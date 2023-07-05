"""Streams instrumented with depth and other stats."""

import math
from collections import Counter
from typing import Any
from typing import Union
from typing import cast

# third-party imports
import anyio

from .common import INDEX_KEY
from .common import RATE_ROUNDING
from .common import SIMPLE_TYPES
from .common import TIME_EPSILON
from .common import MillisecondTimer


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
        worker_name: Union[str, None] = None,
        worker_count: Union[int, None] = None,
    ):
        """Put on results queue and update stats."""
        worker_name = cast(str, worker_name)
        worker_count = cast(int, worker_count)
        async with self._lock:
            del self.inflight[worker_name][worker_count]
        await self.send_stream.send(args)

    async def get(self, /, worker_name: Union[str, None] = None, **kwargs):
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
        worker_name: Union[str, None] = None,
        worker_count: Union[int, None] = None,
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
