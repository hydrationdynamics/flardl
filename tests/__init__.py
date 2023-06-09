"""Test suite for the flardl package."""
from __future__ import annotations

import contextlib
import functools
import os
from pathlib import Path
from typing import Callable

import loguru


NO_LEVEL_BELOW = 100
SERVER_DEFS = [
    {
        "name": "aws",
        "server": "s3.rcsb.org",
        "dir": "pub/pdb/data",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_factor": 0,
    },
    {
        "name": "us",
        "server": "files.rcsb.org",
        "dir": "pub/pdb/data",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_factor": 0,
    },
    {
        "name": "br",
        "server": "bmrb.io",
        "dir": "ftp/pub/pdb/data",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_factor": 0,
    },
    {
        "name": "uk",
        "server": "ftp.ebi.ac.uk",
        "dir": "pub/databases/pdb/data",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_factor": 0,
    },
    {
        "name": "jp",
        "server": "files.pdbj.org",
        "dir": "pub/pdb/data",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_factor": 0,
    },
]


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


def stderr_format_func(record: loguru.Record) -> str:
    """Do level-sensitive formatting."""
    if record["level"].no < NO_LEVEL_BELOW:
        return "<level>{message}</level>\n"
    return "<level>{level}</level>: <level>{message}</level>\n"
