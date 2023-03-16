"""Test suite for the flardl package."""
import contextlib
import functools
import os
from pathlib import Path
from typing import Callable


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
