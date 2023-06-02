"""Work is dispatched to multiple workers and results collected via asynchio queues."""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from typing import Any
from typing import Union
from typing import cast

# third-party imports
import loguru
from loguru import logger as mylogger

from . import DEFAULT_MAX_RETRIES
from . import INDEX_KEY
from . import RATE_ROUNDING
from . import TIME_EPSILON
from . import MillisecondTimer
from .queue_stats import QueueStats


SIMPLE_TYPES = Union[int, float, str, None]


def get_index_value(item: dict[str, SIMPLE_TYPES]) -> int:
    """Return value of index key."""
    return cast(int, item[INDEX_KEY])


class ArgumentQueue(asyncio.Queue):
    """A queue of dictionaries to be used as arguments."""

    def __init__(
        self,
        arg_list: list[dict[str, SIMPLE_TYPES]],
        in_process: dict[str, Any],
        timer: MillisecondTimer,
        /,
        maxsize: int = 0,
    ):
        """Initialize data structure for in-flight stats."""
        super().__init__(maxsize)
        for args in arg_list:
            self.put_nowait(args)
        self.n_args = len(arg_list)
        self.inflight = in_process
        self.timer = timer
        self.launch_rate = 0.0
        self.worker_counter: Counter[str] = Counter()
        self._lock = asyncio.Lock()

    async def put(
        self,
        args,
        /,
        worker_name: str | None = None,
        worker_count: int | None = None,
    ):
        """Put on results queue and update stats."""
        worker_name = cast(str, worker_name)
        worker_count = cast(int, worker_count)
        async with self._lock:
            del self.inflight[worker_name][worker_count]
        await super().put(args)

    async def get(self, /, worker_name: str | None = None, **kwargs):
        """Track de-queuing by worker."""
        worker_name = cast(str, worker_name)
        q_entry = await super().get(**kwargs)
        async with self._lock:
            self.worker_counter[worker_name] += 1
            worker_count = self.worker_counter[worker_name]
            if worker_name not in self.inflight:
                self.inflight[worker_name] = {}
            idx = q_entry[INDEX_KEY]
            launch_time = self.timer.time()
            self.launch_rate = round(
                idx * 1000.0 / (launch_time + TIME_EPSILON), RATE_ROUNDING
            )
            self.inflight[worker_name][worker_count] = {
                INDEX_KEY: idx,
                "queue_depth": len(self.inflight[worker_name]),
                "launch_ms": launch_time,
                "cum_launch_rate": self.launch_rate,
            }
        return q_entry, worker_count


class ResultsQueue(asyncio.Queue):
    """A queue with method to produce an ordered list of results."""

    def __init__(
        self,
        in_process: dict[str, Any],
        timer: MillisecondTimer,
        /,
        maxsize: int = 0,
    ) -> None:
        """Init stats for queue."""
        super().__init__(maxsize)
        self.inflight = in_process
        self.count = 0
        self.timer = timer
        self._lock = asyncio.Lock()

    async def put(
        self,
        args,
        /,
        worker_name: str | None = None,
        worker_count: int | None = None,
    ):
        """Put on results queue and update stats."""
        worker_name = cast(str, worker_name)
        worker_count = cast(int, worker_count)
        launch_stats = self.inflight[worker_name][worker_count]
        for result_name in ["launch_ms"]:
            args[result_name] = launch_stats[result_name]
        async with self._lock:
            del self.inflight[worker_name][worker_count]
        await super().put(args)

    def get_results(self) -> list[dict[str, SIMPLE_TYPES]]:
        """Return sorted list of queue contents."""
        fail_list = []
        while not self.empty():
            fail_list.append(self.get_nowait())
        self.count = len(fail_list)
        return sorted(fail_list, key=get_index_value)


class FailureQueue(asyncio.Queue):
    """A queue to track failures."""

    def __init__(
        self,
        in_process: dict[str, Any],
        timer: MillisecondTimer,
        /,
        maxsize: int = 0,
    ) -> None:
        """Init stats for queue."""
        super().__init__(maxsize)
        self.inflight = in_process
        self.count = 0
        self.timer = timer
        self._lock = asyncio.Lock()

    async def put(
        self,
        args,
        /,
        worker_name: str | None = None,
        worker_count: int | None = None,
    ):
        """Put on results queue and update stats."""
        worker_name = cast(str, worker_name)
        worker_count = cast(int, worker_count)
        async with self._lock:
            del self.inflight[worker_name][worker_count]
        await super().put(args)

    def get_results(self) -> list[dict[str, SIMPLE_TYPES]]:
        """Return sorted list of queue contents."""
        fail_list = []
        while not self.empty():
            fail_list.append(self.get_nowait())
        self.count = len(fail_list)
        return sorted(fail_list, key=get_index_value)


class InstrumentedQueues:
    """Queues that track processing time and results."""

    def __init__(
        self,
        arg_list: list[dict[str, Any]],
        /,
        maxsize: int = 0,
    ):
        """Initialize queues and instrumentation."""
        self.inflight: dict[str, SIMPLE_TYPES] = {}
        self.timer = MillisecondTimer()
        self.argument_queue = ArgumentQueue(arg_list, self.inflight, self.timer)
        self.results_queue = ResultsQueue(self.inflight, self.timer)
        self.failed_queue = FailureQueue(self.inflight, self.timer)
        self.n_args = self.argument_queue.n_args

    def stats(self):
        """Report per-worker and global stats."""
        stat_dict = {
            "jobs_in": self.n_args,
            "finished": self.results_queue.count,
            "failed": self.failed_queue.count,
            "workers": len(self.inflight),
        }
        return stat_dict


class MultiDispatcher:
    """Runs multiple downloaders using aynchio queues."""

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
        self.queue_stats = QueueStats(worker_list, history_len=history_len)
        self._lock = asyncio.Lock()

    async def run(self, arg_list: list[dict[str, SIMPLE_TYPES]]):
        """Run the multidispatcher queue."""
        queues = InstrumentedQueues(arg_list)
        arg_q = queues.argument_queue
        result_q = queues.results_queue
        failed_q = queues.failed_queue
        dispatchers = [
            asyncio.create_task(self.dispatcher(w, arg_q, result_q, failed_q))
            for w in self.workers
        ]

        # Wait until all requests are done.
        await arg_q.join()

        # Cancel dispatchers waiting for arguments.
        [d.cancel() for d in dispatchers]

        # Wait until all dispatchers are cancelled.
        await asyncio.gather(*dispatchers, return_exceptions=True)

        # Process results into pandas data frame in input order.
        results = result_q.get_results()
        fails = failed_q.get_results()
        stats = queues.stats()
        return results, fails, stats

    async def dispatcher(
        self,
        worker,
        arg_q: ArgumentQueue,
        result_q: ResultsQueue,
        failed_q: FailureQueue,
    ):
        """Dispatch tasks to worker functions and handle exceptions."""
        while True:
            # Get a set of arguments from the queue.
            kwargs, worker_count = await arg_q.get(worker_name=worker.name)
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
                        idx, worker.name, worker_count, e, failed_q
                    )
                else:
                    await worker.soft_exception_handler(
                        kwargs, worker.name, worker_count, e, arg_q
                    )
            except worker.hard_exceptions as e:
                idx = kwargs[INDEX_KEY]
                await worker.hard_exception_handler(
                    idx, worker.name, worker_count, e, failed_q
                )
            except Exception as e:
                # unhandled errors are fatal
                idx = kwargs[INDEX_KEY]
                await worker.fatal_exception_handler(idx, e)
            # Notify the queue that the item has been processed.
            arg_q.task_done()

    def main(self, arg_list: list[dict[str, SIMPLE_TYPES]]):
        """Start the multidispatcher queue."""
        return asyncio.run(self.run(arg_list))


class QueueWorker:
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
        result_q: ResultsQueue,
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
        failed_q: FailureQueue,
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
        await failed_q.put(
            failure_entry, worker_name=worker_name, worker_count=worker_count
        )

    async def fatal_exception_handler(self, index: int, error: Exception):
        """Handle fatal exceptions."""
        self._logger.error(error)
        await self._logger.complete()
        sys.exit(1)

    async def soft_exception_handler(
        self,
        kwargs: dict[str, Any],
        worker_name: str,
        worker_count: int,
        error: Exception,
        arg_q: ArgumentQueue,
    ):
        """Handle exceptions that re-try arguments."""
        if not self.quiet:
            self._logger.warning(error)
        await arg_q.put(kwargs, worker_name=worker_name, worker_count=worker_count)
