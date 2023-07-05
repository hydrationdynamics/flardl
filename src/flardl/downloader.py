"""Downloads as a MultiDispatcher worker class."""
from __future__ import annotations

import sys
from typing import Any

# third-party imports
import anyio
import loguru
from loguru import logger as mylogger

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
        self, name: str, logger: loguru.Logger | None = None, quiet: bool = False
    ):
        """Init data structures."""
        if logger is None:
            self._logger = mylogger
        else:
            self._logger = logger
        self.name = name
        self.n_soft_fails = 0
        self.n_hard_fails = 0
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = ()
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = ()
        self.work_qty_name = "bytes"
        self.quiet = quiet

    async def queue_results(
        self,
        result_q: ResultStream,
        worker_count: int,
        idx: int,
        work_qty: float | int,
        /,
        **kwargs: SIMPLE_TYPES,
    ):
        """Put dictionary of results on ouput queue."""
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

    def __init__(
        self,
        ident_no: int,
        logger: loguru.Logger | None = None,
        quiet: bool = False,
        write_file: bool = False,
    ):
        """Init with id number."""
        super().__init__(f"W{ident_no}", logger=logger, quiet=quiet)
        self.quiet = quiet
        self.ident = ident_no
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = (ValueError,)
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = (
            ConnectionError,
        )
        self.work_qty_name = "bytes"
        self.launch_rate = self.LAUNCH_RATE_MAX / (ident_no + 1.0)
        self.retirement_rate = self.launch_rate / self.LAUNCH_RETIREMENT_RATIO
        self.output_path = anyio.Path("./tmp")
        self.write_file = write_file
        self._lock = anyio.Lock()
        self._limiter_delay = RandomValueGenerator().get_wait_time
        self._simulated_bytes = RandomValueGenerator().zipf_with_min
        self._simulated_dl_time = RandomValueGenerator().get_wait_time

    async def limiter(self):
        """Fake rate-limiting via sleep for a time dependent on worker."""
        await anyio.sleep(self._limiter_delay(self.launch_rate))

    async def worker(
        self,
        result_q: ResultStream,
        worker_count: int,
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
        # write fake output
        dl_bytes = self._simulated_bytes()
        if self.write_file:
            filename = str(code) + "." + str(file_type)
            await self.output_path.mkdir(parents=True, exist_ok=True)
            async with await anyio.open_file(
                self.output_path / filename, mode="w"
            ) as f:
                await f.write("a" * dl_bytes)
        # simulate download time with a sleep
        latency = self._simulated_dl_time(self.retirement_rate)
        receive_time = int(dl_bytes / self.DL_CHUNK_SIZE) / self.DL_RATE
        dl_time = round(latency + receive_time, self.TIME_ROUND)
        await anyio.sleep(dl_time)
        await self.queue_results(
            result_q, worker_count, idx, dl_bytes, filename=filename
        )
