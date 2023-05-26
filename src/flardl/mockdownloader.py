"""Mock downloads using sleeps."""
from __future__ import annotations

import asyncio

# third-party imports
import loguru

# module imports
from . import random_value_generator as rng
from .multidispatcher import QueueWorker
from .multidispatcher import ResultsQueue


ZIPF_EXPONENT = 1.4
ZIPF_SCALE = 1000
ZIPF_MIN = 1024


class MockDownloader(QueueWorker):
    """Demonstrates multi-dispatch operation with logging."""

    SOFT_FAILS = [2, 4]
    RESCUE_SOFT_FAILS = (4,)
    HARD_FAILS = (
        6,
        9,
    )
    LAUNCH_RETIREMENT_RATIO = 1.0
    LAUNCH_RATE_MAX = 100.0

    def __init__(
        self, ident_no: int, logger: loguru.Logger | None = None, quiet: bool = False
    ):
        """Init with id number."""
        super().__init__(f"Worker{ident_no}", logger=logger, quiet=quiet)
        self.quiet = quiet
        self.ident = ident_no
        self.hard_exceptions: tuple[()] | tuple[type[BaseException]] = (ValueError,)
        self.soft_exceptions: tuple[()] | tuple[type[BaseException]] = (
            ConnectionError,
        )
        self.work_qty_name = "bytes"
        self.launch_rate = self.LAUNCH_RATE_MAX / (ident_no + 1.0)
        self.retirement_rate = self.launch_rate / self.LAUNCH_RETIREMENT_RATIO

    async def limiter(self):
        """Fake rate-limiting via sleep for a time dependent on worker."""
        await asyncio.sleep(rng.get_wait_time(self.launch_rate))

    async def worker(
        self,
        result_q: ResultsQueue,
        worker_count: int,
        idx: int,
        int_arg: int | None = None,
        str_arg: str | None = None,
        float_arg: float | None = None,
        short_arg: list | None = None,
    ):
        """Do a work unit."""
        if idx in self.SOFT_FAILS:
            async with asyncio.Lock():
                self.n_soft_fails += 1
                if idx in self.RESCUE_SOFT_FAILS:
                    self.SOFT_FAILS.remove(idx)
            raise ConnectionError(f"{self.name} aborted job {idx} (expected).")
        elif idx in self.HARD_FAILS:
            async with asyncio.Lock():
                self.n_hard_fails += 1
            raise ValueError(f"Job {idx} failed on {self.name} (expected).")
        elif not self.quiet:
            self._logger.info(f"{self.name} working on job {idx}...")
        # Put results on out queue
        work_qty = rng.zipf_with_min(
            minimum=ZIPF_MIN, scale=ZIPF_SCALE, exponent=ZIPF_EXPONENT
        )
        # simulate work with a sleep
        await asyncio.sleep(rng.get_wait_time(self.retirement_rate))
        await self.queue_results(result_q, worker_count, idx, work_qty, label=str_arg)
