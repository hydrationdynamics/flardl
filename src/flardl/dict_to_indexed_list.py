"""Zip a dict of lists to an indexed list of dicts."""

import abc
from collections.abc import Iterable
from itertools import zip_longest
from typing import Union
from typing import cast

import _collections_abc as cabc

from .common import INDEX_KEY
from .common import SIMPLE_TYPES


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


def zip_dict_to_indexed_list(
    arg_dict: dict[str, Union[NonStringIterable, SIMPLE_TYPES]]
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
