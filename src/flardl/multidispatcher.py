"""Work is dispatched to multiple workers and results collected via asynchio queues."""
from __future__ import annotations

import math
import sys
from collections import Counter
from typing import Any
from typing import Union
from typing import cast

# third-party imports
import anyio
import loguru
from loguru import logger as mylogger

from .common import DEFAULT_MAX_RETRIES
from .common import INDEX_KEY
from .common import RATE_ROUNDING
from .common import TIME_EPSILON
from .common import MillisecondTimer
from .queue_stats import QueueStats


SIMPLE_TYPES = Union[int, float, str, None]
LAUNCH_KEY = "launch_t"


def get_index_value(item: dict[str, SIMPLE_TYPES]) -> int:
    """Return value of index key."""
    return cast(int, item[INDEX_KEY])


class ArgumentStream:
    """A stream of dictionaries to be used as arguments."""

    def __init__(
        self,
        arg_list: list[dict[str, SIMPLE_TYPES]],
        in_process: dict[str, Any],
        timer: MillisecondTimer,
    ):
        """Initialize data structure for in-flight stats."""
        self.send_stream, self.receive_stream = anyio.create_memory_object_stream(
            max_buffer_size=math.inf
        )
        for args in arg_list:
            self.send_stream.send_nowait(args)
        self.n_args = len(arg_list)
        self.inflight = in_process
        self.timer = timer
        self.launch_rate = 0.0
        self.worker_counter: Counter[str] = Counter()
        self._lock = anyio.Lock()

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
        await self.send_stream.send(args)

    async def get(self, /, worker_name: str | None = None, **kwargs):
        """Track de-queuing by worker."""
        worker_name = cast(str, worker_name)
        q_entry = self.receive_stream.receive_nowait(**kwargs)
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
                LAUNCH_KEY: launch_time,
                "cum_launch_rate": self.launch_rate,
            }
        return q_entry, worker_count


class FailureStream:
    """Anyio stream to track failures."""

    launch_stats_out: list[str] = []

    def __init__(
        self,
        in_process: dict[str, Any],
    ) -> None:
        """Init stats for queue."""
        self.send_stream, self.receive_stream = anyio.create_memory_object_stream(
            max_buffer_size=math.inf
        )
        self.inflight = in_process
        self.count = 0
        self._lock = anyio.Lock()

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
        for result_name in self.launch_stats_out:
            args[result_name] = launch_stats[result_name]
        async with self._lock:
            self.count += 1
            del self.inflight[worker_name][worker_count]
        await self.send_stream.send(args)

    def get_all(self) -> list[dict[str, SIMPLE_TYPES]]:
        """Return sorted list of stream contents."""
        stream_contents = []
        while True:
            try:
                stream_contents.append(self.receive_stream.receive_nowait())
            except anyio.WouldBlock:
                break
        return sorted(stream_contents, key=get_index_value)


class ResultStream(FailureStream):
    """Stream for results."""

    launch_stats_out = [LAUNCH_KEY]


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
        self.queue_stats = QueueStats(worker_list, history_len=history_len)
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
