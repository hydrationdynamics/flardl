"""Downloads as a MultiDispatcher worker class."""
from __future__ import annotations

import pathlib
import sys
from typing import Any

# third-party imports
import anyio
import httpx
import loguru

# module imports
from .common import INDEX_KEY
from .common import SIMPLE_TYPES
from .common import RandomValueGenerator
from .instrumented_streams import ArgumentStream
from .instrumented_streams import FailureStream
from .instrumented_streams import ResultStream


class StreamWorker:
    """Basic worker functions."""

    def __init__(
        self,
        worker_no: int,
        logger: loguru.Logger,
        output_dir: str | None,
        quiet: bool,
        /,
        name: str,
        bw_limit_mbps: float = 0.0,
        queue_depth: int = 0,
        timeout_factor: float = 0.0,
        **kwargs,
    ):
        """Positional=common across workers, keyworded=individual."""
        self.worker_no = worker_no
        self.output_dir = output_dir
        self._logger = logger
        self.output_dir = output_dir
        if output_dir is not None:
            pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
        self.quiet = quiet
        # keyworded parameters
        self.name = name

        self.bw_limit = bw_limit_mbps
        self.queue_depth = queue_depth
        self.timeout_factor = timeout_factor
        # initialize internal parameters
        self.work_qty_name = "bytes"
        self.n_soft_fails = 0
        self.n_hard_fails = 0
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = ()
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = ()
        self._lock = anyio.Lock()
        self._limiter_delay = RandomValueGenerator().get_wait_time

    async def limiter(self):
        """Fake rate-limiting via sleep."""
        await anyio.sleep(self._limiter_delay(self.launch_rate))

    async def add_result(
        self,
        data: bytes | str,
        filename: str,
        idx: int,
        worker_count: int,
        result_q: ResultStream,
        /,
        **kwargs: dict[str, SIMPLE_TYPES],
    ):
        """Put dictionary of results on ouput queue."""
        work_qty = len(data)
        if self.output_dir is not None:
            out_file_str = self.output_dir + "/" + filename
            if isinstance(data, str):
                async with await anyio.open_file(out_file_str, "w") as fp:
                    await fp.write(data)
            else:
                out_file_path = anyio.Path(out_file_str)
                await out_file_path.write_bytes(data)
        results = {
            INDEX_KEY: idx,
            "worker": self.name,
            self.work_qty_name: work_qty,
        }
        results.update(kwargs)
        await result_q.put(results, worker_name=self.name, worker_count=worker_count)

    async def hard_exception_handler(
        self,
        index: int,
        worker_name: str,
        worker_count: int,
        error: Exception,
        failure_q: FailureStream,
    ):
        """Handle exceptions that re-queue arguments as failed."""
        if error.__class__ in self.soft_exceptions:
            message = repr(error)
            error_name = "TooManyRetries"
        else:
            message = str(error)
            error_name = error.__class__.__name__
        if not self.quiet:
            self._logger.error(f"{error_name}: {message}")
        failure_entry = {
            INDEX_KEY: index,
            "worker": worker_name,
            "error": error_name,
            "message": message,
        }
        await failure_q.put(
            failure_entry, worker_name=worker_name, worker_count=worker_count
        )

    async def unhandled_exception_handler(self, index: int, error: Exception):
        """Handle unhandled exceptions."""
        self._logger.error(error)
        await self._logger.complete()
        sys.exit(1)

    async def soft_exception_handler(
        self,
        kwargs: dict[str, Any],
        worker_name: str,
        worker_count: int,
        error: Exception,
        arg_q: ArgumentStream,
    ):
        """Handle exceptions that re-try arguments."""
        if not self.quiet:
            self._logger.warning(error)
        await arg_q.put(kwargs, worker_name=worker_name, worker_count=worker_count)


class MockDownloader(StreamWorker):
    """Demonstrates multi-dispatch operation with logging."""

    SOFT_FAILS = [2, 4]
    RESCUE_SOFT_FAILS = (4,)
    HARD_FAILS = (
        6,
        9,
    )
    LAUNCH_RETIREMENT_RATIO = 1.0
    LAUNCH_RATE_MAX = 100.0
    DL_RATE = 10000  # chunks/sec
    DL_CHUNK_SIZE = 1500  # bytes per chunk (packet)
    TIME_ROUND = 4

    def __init__(self, *args, **kwargs):
        """Init with id number."""
        super().__init__(*args, **kwargs)
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = (ValueError,)
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = (
            ConnectionError,
        )
        self.launch_rate = self.LAUNCH_RATE_MAX / (self.worker_no + 1.0)
        self.retirement_rate = self.launch_rate / self.LAUNCH_RETIREMENT_RATIO
        self._simulated_bytes = RandomValueGenerator().zipf_with_min
        self._simulated_dl_time = RandomValueGenerator().get_wait_time

    async def worker(
        self,
        result_q: ResultStream,
        worker_count: int,
        /,
        idx: int,
        code: str | None = None,
        file_type: str | None = None,
    ):
        """Do a work unit."""
        if idx in self.SOFT_FAILS:
            async with self._lock:
                self.n_soft_fails += 1
                if idx in self.RESCUE_SOFT_FAILS:
                    self.SOFT_FAILS.remove(idx)
            raise ConnectionError(f"{self.name} aborted job {idx} (expected).")
        elif idx in self.HARD_FAILS:
            async with self._lock:
                self.n_hard_fails += 1
            raise ValueError(f"Job {idx} failed on {self.name} (expected).")
        elif not self.quiet:
            self._logger.info(f"{self.name} working on job {idx}...")
        # create simulated output
        n_dl_bytes = self._simulated_bytes()
        dl_data = "a" * n_dl_bytes
        filename = str(code) + "." + str(file_type)
        # simulate download time with a sleep
        latency = self._simulated_dl_time(self.retirement_rate)
        receive_time = int(n_dl_bytes / self.DL_CHUNK_SIZE) / self.DL_RATE
        dl_time = round(latency + receive_time, self.TIME_ROUND)
        await anyio.sleep(dl_time)
        out_filename = filename
        await self.add_result(dl_data, out_filename, idx, worker_count, result_q)


class Downloader(StreamWorker):
    """Demonstrates multi-dispatch operation with logging."""

    LAUNCH_RATE_MAX = 100.0
    TIME_ROUND = 4

    def __init__(
        self,
        *args,
        server: str,
        dir: str,
        transport: str,
        transport_ver: str,
        bw_limit_mbps: float,
        queue_depth: int,
        timeout_s: float,
        **super_kwargs,
    ):
        """Init with id number."""
        super().__init__(*args, **super_kwargs)
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = (
            httpx.HTTPStatusError,
        )
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = (ValueError,)
        self.launch_rate = self.LAUNCH_RATE_MAX
        self.base_url = transport + "://" + server + "/"
        if dir != "":
            self.base_url += dir + "/"
        if transport_ver == "2":
            self.http2 = True
        else:
            self.http2 = False
        self.client = httpx.AsyncClient(
            base_url=self.base_url, http2=self.http2, timeout=timeout_s
        )

    async def worker(
        self,
        result_q: ResultStream,
        worker_count: int,
        /,
        idx: int,
        path: str,
        out_filename: str,
    ):
        """Download a file."""
        response = await self.client.get(path)
        if response.status_code != httpx.codes.OK:
            response.raise_for_status()
        dl_data = response.content
        if not self.quiet:
            print(out_filename)
        await self.add_result(dl_data, out_filename, idx, worker_count, result_q)
