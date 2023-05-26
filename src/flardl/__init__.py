"""Flardl--download list of URLs from a list of federated servers."""
import abc
import asyncio
from time import time
from typing import Optional
from typing import Union

import _collections_abc as cabc

# third-party imports
import numpy as np


# The following globals are also attribute names,
# don't change one without the other.
ALL = "all"
AVG = "avg"
HIST = "history"
MAX = "max"
MIN = "min"
NOBS = "n_obs"
RAVG = "r_avg"
SUM = "sum"
VALUE = "value"
# pretty labels for substat names
STAT_SUBLABELS = {
    VALUE: "",
    SUM: "total ",
    AVG: "average ",
    MIN: "min ",
    MAX: "max ",
    NOBS: "# ",
    HIST: "history ",
    RAVG: "rolling average ",
}
INDEX_KEY = "idx"
# constants
DEFAULT_ROUNDING = 2  # digits after decimal
DEFAULT_MAX_RETRIES = 0
TIME_ROUNDING = 1  # digits, milliseconds
RATE_ROUNDING = 1  # digits, inverse seconds
TIME_EPSILON = 0.01  # milliseconds
BYTES_TO_MEGABITS = 8.0 / 1024.0 / 1024.0
RANDOM_SEED = 47
DEFAULT_ZIPF_EXPONENT = 1.3
# type defs
NUMERIC_TYPE = Union[int, float]
OPTIONAL_NUMERIC = Optional[NUMERIC_TYPE]
OPTIONAL_NUMERIC_LIST = Union[OPTIONAL_NUMERIC, list[NUMERIC_TYPE]]
TIME_ROUNDING = 1  # digits, milliseconds


class RandomValueGenerator:
    """Seeded, reproducible random-value generation."""

    def __init__(self, seed: int = RANDOM_SEED):
        """Init random value generator with seed."""
        self.rng = np.random.default_rng(seed)

    def get_wait_time(self, rate: float) -> float:
        """Given rate, return wait time from an exponential distribution."""
        return self.rng.exponential(1.0 / rate)

    def zipf_with_min(
        self, minimum: int = 0, scale: int = 1, exponent: float = DEFAULT_ZIPF_EXPONENT
    ) -> int:
        """Return a Zipf's law-distributed integer with minimum.

        This distribution approximately describes many file-size
        distributions arising from natural language and human-written
        code (though code standards discourage large files). It
        is a sensitive function of the exponent, with exponents
        near 1.0 generating a higher divergence. For exponents
        greater than 2, there is only a small likelihood of
        finding a 2-digit value in a sample of size 100; for
        an exponent of 1.1, most values will have multiple digits.
        The default value is chosen to give a reasonable range
        in a sample of a few thousand.

        Note that the first moment of this power-law
        distribution tends to increase with sample size.
        If used in a mock downloader as a sample size, this
        implies the mean per-file download rate goes down
        with the number of files downloaded because the chances
        of hitting a big file goes up.
        """
        return minimum + scale * self.rng.zipf(exponent)


random_value_generator = RandomValueGenerator()


class NonStringIterable(metaclass=abc.ABCMeta):
    """A class to find iterables that are not strings."""

    __slots__ = ()

    @abc.abstractmethod
    def __iter__(self):
        """Fake iteration."""
        while False:
            yield None

    @classmethod
    def __subclasshook__(cls, c):
        """Check if non-string iterable."""
        if cls is NonStringIterable:
            if issubclass(c, str):
                return False

            return cabc._check_methods(c, "__iter__")
        return NotImplemented


class MillisecondTimer:
    """Give the time in milliseconds since initialization."""

    def __init__(self) -> None:
        """Init the start_time."""
        self.start_time = time()

    def time(self) -> float:
        """Return time from start in milliseconds."""
        return round((time() - self.start_time) * 1000.0, TIME_ROUNDING)
