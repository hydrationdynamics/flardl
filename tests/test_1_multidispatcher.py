"""Test multidispatcher function with mock downloader."""
from __future__ import annotations

import sys

# third-party imports
import loguru
import pandas as pd
import pytest

from flardl import INDEX_KEY
from flardl import MultiDispatcher

from . import stderr_format_func


ANYIO_BACKEND = "asyncio"


@pytest.fixture
def anyio_backend():
    """Select backend for testing."""
    return ANYIO_BACKEND


@pytest.mark.anyio
async def test_anyio_multidispatcher() -> None:
    """Test multidispatcher."""
    n_items = 100
    n_consumers = 3
    max_retries = 2
    quiet = True
    worker_defs = [{"name": f"W{i}"} for i in range(n_consumers)]
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=stderr_format_func)
    logger.info("1")
    runner = MultiDispatcher(
        worker_defs,
        logger=logger,
        max_retries=max_retries,
        quiet=quiet,
        write_files=True,
    )
    logger.info("2")
    arg_dict = {
        "code": [f"{i:04}" for i in range(n_items)],
        "file_type": "txt",
    }
    result_list, fail_list, global_stats = await runner.run(arg_dict)
    results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
    print(f"\nResults:\n{results}")
    results.to_csv("results.tsv", sep="\t")
    failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
    print(f"\nFailures:\n{failures}")
    print(f"\nGlobal Stats:\n{global_stats}")
