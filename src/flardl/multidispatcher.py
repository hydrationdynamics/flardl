"""Work is dispatched to multiple workers and results collected via AnyIO streams."""
from __future__ import annotations

import sys
from typing import Optional

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
