"""Dispatch work to multiple workers and collect results via AnyIO streams."""
from __future__ import annotations

import sys
from typing import Any

# third-party imports
import anyio
import httpx
import loguru
from loguru import logger as mylogger

from .common import DEFAULT_MAX_RETRIES
from .common import INDEX_KEY
from .common import SIMPLE_TYPES
from .common import MillisecondTimer
from .dict_to_indexed_list import NonStringIterable
from .dict_to_indexed_list import zip_dict_to_indexed_list
from .downloader import Downloader
from .downloader import MockDownloader
from .instrumented_streams import ArgumentStream
from .instrumented_streams import FailureStream
from .instrumented_streams import ResultStream
from .server_defs import ServerDef
from .stream_stats import StreamStats


class MultiDispatcher:
    """Runs multiple single-site dispatchers sharing streams."""

    def __init__(  # noqa: C901
        self,
        all_worker_defs: list[ServerDef],
        /,
        worker_list: list[str] | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        logger: loguru.Logger | None = None,
        quiet: bool = False,
        history_len: int = 0,
        output_dir: str | None = None,
        mock: bool = False,
        runner: str = "production",
    ) -> None:
        """Save list of dispatchers."""
        if logger is None:
            self._logger = mylogger
        else:
            self._logger = logger
        all_worker_names = [w.name for w in all_worker_defs]
        if worker_list is None:
            worker_defs = all_worker_defs
        else:
            worker_defs = []
            for worker_name in worker_list:
                try:
                    worker_idx = all_worker_names.index(worker_name)
                except ValueError:
                    self._logger.error(f"Worker name {worker_name} not found.")
                    sys.exit(1)
                worker_defs.append(all_worker_defs[worker_idx])
        self.workers = []
        worker_factory: type[MockDownloader | Downloader] = Downloader
        if mock:
            worker_factory = MockDownloader
        for i, worker_def in enumerate(worker_defs):
            try:
                worker = worker_factory(
                    i, self._logger, output_dir, quiet, **worker_def.get_all()  # type: ignore
                )
            except Exception as e:
                self._logger.warning(f"Worker {worker_def.name} failed to initialize.")
                self._logger.warning(e)
                continue
            self.workers.append(worker)
        if len(self.workers) == 0:
            self._logger.error("No valid workers found.")
            sys.exit(1)
        self.max_retries = max_retries
        self.backend_options = {}
        if runner == "production":
            self.backend = "asyncio"
            if sys.platform != "win32":
                self.backend_options = {"use_uvloop": True}
        elif runner == "testing":
            self.backend = "asyncio"
            # asyncio.set_event_loop_policy(DeterministicEventLoopPolicy())
        elif runner == "trio":
            self.backend = "trio"
        else:
            self._logger.error(f"Unknown runner configuration {runner}")
            sys.exit(1)
        self.exception_counter: dict[int, int] = {}
        self.n_too_many_retries = 0
        self.n_exceptions = 0
        self.quiet = quiet
        self.queue_stats = StreamStats(all_worker_names, history_len=history_len)
        self._lock = anyio.Lock()
        self.inflight: dict[str, SIMPLE_TYPES] = {}
        self.timer = MillisecondTimer()

    async def run(
        self,
        args: (
            list[dict[str, SIMPLE_TYPES]] | dict[str, NonStringIterable | SIMPLE_TYPES]
        ),
    ):
        """Run the multidispatcher queue."""
        if isinstance(args, list):
            arg_list = args
        elif isinstance(args, dict):
            arg_list = zip_dict_to_indexed_list(args)
        arg_q = ArgumentStream(arg_list, self.inflight, self.timer)
        result_stream = ResultStream(self.inflight)
        failure_stream = FailureStream(self.inflight)

        async with anyio.create_task_group() as tg:
            for worker in self.workers:
                tg.start_soon(
                    self.dispatcher, worker, arg_q, result_stream, failure_stream
                )

        # Process results into pandas data frame in input order.
        results = result_stream.get_all()
        fails = failure_stream.get_all()
        stats = {
            "requests": len(arg_list),
            "downloaded": len(results),
            "failed": len(fails),
            "workers": len(self.workers),
        }
        return results, fails, stats

    async def dispatcher(  # noqa: C901
        self,
        worker,
        arg_q: ArgumentStream,
        result_q: ResultStream,
        failure_q: FailureStream,
    ):
        """Dispatch tasks to worker functions and handle exceptions."""
        while True:
            try:
                # Get a set of arguments from the queue.
                kwargs, worker_count = await arg_q.get(worker_name=worker.name)
            except anyio.WouldBlock:
                return
            if worker_count > 0:
                # Do rate limiting, if a limiter is found in worker.
                try:
                    await worker.limiter()
                except AttributeError:
                    pass  # it's okay if worker didn't have a limiter
            # Do the work and handle any exceptions encountered.
            try:
                await worker.worker(result_q, worker_count, **kwargs)
            except worker.soft_exceptions as e:
                # Errors to be requeued by worker, unless too many
                async with self._lock:
                    idx = kwargs[INDEX_KEY]
                    self.n_exceptions += 1
                    if idx not in self.exception_counter:
                        self.exception_counter[idx] = 1
                    else:
                        self.exception_counter[idx] += 1
                    n_exceptions = self.exception_counter[idx]
                if self.max_retries > 0 and n_exceptions >= self.max_retries:
                    await worker.hard_exception_handler(
                        idx, worker.name, worker_count, e, failure_q
                    )
                else:
                    await worker.soft_exception_handler(
                        kwargs, worker.name, worker_count, e, arg_q
                    )
            except worker.hard_exceptions as e:
                idx = kwargs[INDEX_KEY]
                await worker.hard_exception_handler(
                    idx, worker.name, worker_count, e, failure_q
                )
            except httpx.ConnectError:
                await worker.soft_exception_handler(
                    kwargs,
                    worker.name,
                    worker_count,
                    f"Server '{worker.name!r}' shutdown due to ConnectError",
                    arg_q,
                )
                return
            except Exception as e:
                # unhandled errors go to unhandled exception handler
                idx = kwargs[INDEX_KEY]
                await worker.unhandled_exception_handler(idx, e)

    def main(
        self,
        arg_list: list[dict[str, SIMPLE_TYPES]]
        | dict[str, NonStringIterable | SIMPLE_TYPES],
    ):
        """Start the multidispatcher queue."""
        return anyio.run(
            self.run,
            arg_list,
            backend=self.backend,
            backend_options=self.backend_options,
        )
