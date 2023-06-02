"""Test multidispatcher function with mock downloader."""
from __future__ import annotations

import abc
import sys
from collections.abc import Iterable
from itertools import zip_longest
from typing import cast

import _collections_abc as cabc

# third-party imports
import loguru
import pandas as pd

from flardl import INDEX_KEY
from flardl import SIMPLE_TYPES
from flardl.mockdownloader import MockDownloader
from flardl.multidispatcher import MultiDispatcher

from . import print_docstring


NO_LEVEL_BELOW = 100


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


def zip_arg_dict(
    arg_dict: dict[str, NonStringIterable | SIMPLE_TYPES]
) -> list[dict[str, SIMPLE_TYPES]]:
    """Zip on the longest non-string iterables, adding an index."""
    ret_list = []
    iterable_args = [k for k in arg_dict if isinstance(arg_dict[k], NonStringIterable)]
    idx = 0
    for iter_tuple in zip_longest(
        *[cast(Iterable, arg_dict[k]) for k in iterable_args]
    ):
        args: dict[str, SIMPLE_TYPES] = {INDEX_KEY: idx}
        for key in arg_dict.keys():
            if key in iterable_args:
                args[key] = iter_tuple[iterable_args.index(key)]
            else:
                args[key] = cast(SIMPLE_TYPES, arg_dict[key])
        idx += 1
        ret_list.append(args)
    return ret_list


def _stderr_format_func(record: loguru.Record) -> str:
    """Do level-sensitive formatting."""
    if record["level"].no < NO_LEVEL_BELOW:
        return "<level>{message}</level>\n"
    return "<level>{level}</level>: <level>{message}</level>\n"


@print_docstring()
def test_multidispatcher():
    """Test multidispatcher."""
    n_items = 100
    n_consumers = 3
    max_retries = 2
    quiet = True
    arg_dict = {
        "code": [f"{i:04}" for i in range(n_items)],
        "file_type": "txt",
    }
    arg_list = zip_arg_dict(arg_dict)
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=_stderr_format_func)
    runner = MultiDispatcher(
        [MockDownloader(i, logger, quiet=quiet) for i in range(n_consumers)],
        max_retries=max_retries,
        quiet=quiet,
    )
    result_list, fail_list, global_stats = runner.main(arg_list)
    results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
    print(f"\nResults:\n{results}")
    results.to_csv("results.tsv", sep="\t")
    failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
    print(f"\nFailures:\n{failures}")
    print(f"\nGlobal Stats:\n{global_stats}")
