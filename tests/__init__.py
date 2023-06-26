"""Test suite for the flardl package."""
from __future__ import annotations

import abc
import contextlib
import functools
import os
from collections.abc import Iterable
from itertools import zip_longest
from pathlib import Path
from typing import Callable
from typing import Union
from typing import cast

import _collections_abc as cabc
import loguru

from flardl import INDEX_KEY


NO_LEVEL_BELOW = 100
SIMPLE_TYPES = Union[int, float, bool, str, None]


@contextlib.contextmanager
def working_directory(path: str) -> None:
    """Change working directory in context."""
    prev_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(prev_cwd)


def print_docstring() -> Callable:
    """Decorator to print a docstring."""

    def decorator(func: Callable) -> Callable:
        """Define decorator."""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            """Print docstring and call function."""
            print(func.__doc__)
            return func(*args, **kwargs)

        return wrapper

    return decorator


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


def stderr_format_func(record: loguru.Record) -> str:
    """Do level-sensitive formatting."""
    if record["level"].no < NO_LEVEL_BELOW:
        return "<level>{message}</level>\n"
    return "<level>{level}</level>: <level>{message}</level>\n"
