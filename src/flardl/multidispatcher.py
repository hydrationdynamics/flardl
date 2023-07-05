"""Work is dispatched to multiple workers and results collected via AnyIO streams."""
from __future__ import annotations

import sys
from typing import Any

# third-party imports
import anyio
import loguru
from loguru import logger as mylogger

from .common import DEFAULT_MAX_RETRIES
from .common import INDEX_KEY
from .common import SIMPLE_TYPES
from .common import MillisecondTimer
from .instrumented_streams import ArgumentStream
from .instrumented_streams import FailureStream
from .instrumented_streams import ResultStream
from .stream_stats import StreamStats


class MultiDispatcher:
    """Runs multiple single-site dispatchers sharing streams."""

    def __init__(
        self,
        worker_list: list,
        /,
        max_retries: int = DEFAULT_MAX_RETRIES,
        logger: loguru.Logger | None = None,
        quiet: bool = False,
        history_len: int = 0,
    ) -> None:
        """Save list of dispatchers."""
        if logger is None:
            self._logger = mylogger
        else:
            self._logger = logger
        self.workers = worker_list
        self.max_retries = max_retries
        self.exception_counter: dict[int, int] = {}
        self.n_too_many_retries = 0
        self.n_exceptions = 0
        self.quiet = quiet
        self.queue_stats = StreamStats(worker_list, history_len=history_len)
        self._lock = anyio.Lock()
        self.inflight: dict[str, SIMPLE_TYPES] = {}
        self.timer = MillisecondTimer()

    async def run(self, arg_list: list[dict[str, SIMPLE_TYPES]]):
        """Run the multidispatcher queue."""
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
                idx = kwargs[INDEX_KEY]
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
            except Exception as e:
                # unhandled errors go to unhandled exception handler
                idx = kwargs[INDEX_KEY]
                await worker.unhandled_exception_handler(idx, e)

    def main(self, arg_list: list[dict[str, SIMPLE_TYPES]], config: str = "production"):
        """Start the multidispatcher queue."""
        backend_options = {}
        if config == "production":
            backend = "asyncio"
            if sys.platform != "win32":
                backend_options = {"use_uvloop": True}
        elif config == "testing":
            backend = "asyncio"
            # asyncio.set_event_loop_policy(DeterministicEventLoopPolicy())
        elif config == "trio":
            backend = "trio"
        else:
            self._logger.error(f"Unknown configuration {config}")
            sys.exit(1)
        return anyio.run(
            self.run, arg_list, backend=backend, backend_options=backend_options
        )


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
