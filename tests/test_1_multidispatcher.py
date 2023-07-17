"""Test multidispatcher function with mock downloader."""

import sys

# third-party imports
import loguru
import pandas as pd
import pytest

from flardl import INDEX_KEY
from flardl import MultiDispatcher

from . import SERVER_DEFS
from . import print_docstring
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
    max_retries = 2
    quiet = True
    server_list = ["aws", "us", "uk"]
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=stderr_format_func)
    runner = MultiDispatcher(
        SERVER_DEFS,
        worker_list=server_list,
        logger=logger,
        max_retries=max_retries,
        quiet=quiet,
        output_dir="./tmp",
        mock=True,
    )
    arg_dict = {
        "code": [f"{i:04}" for i in range(n_items)],
        "file_type": "txt",
    }
    result_list, fail_list, global_stats = await runner.run(arg_dict)
    if len(result_list):
        results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
        print(f"\nResults:\n{results}")
        results.to_csv("results.tsv", sep="\t")
    else:
        logger.error("No results!")
    if len(fail_list):
        failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
        print(f"\nFailures:\n{failures}")
        failures.to_csv("failures.tsv", sep="\t")
    else:
        logger.info("No failures.")
    print(f"\nGlobal Stats:\n{global_stats}")


@print_docstring()
def test_production_multidispatcher() -> None:
    """Test multidispatcheri using indeterminate event loop."""
    n_items = 100
    max_retries = 2
    quiet = True
    server_list = ["aws", "us", "uk"]
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=stderr_format_func)
    runner = MultiDispatcher(
        SERVER_DEFS,
        worker_list=server_list,
        logger=logger,
        max_retries=max_retries,
        quiet=quiet,
        output_dir="./tmp",
        mock=True,
    )
    arg_dict = {
        "code": [f"{i:04}" for i in range(n_items)],
        "file_type": "txt",
    }
    result_list, fail_list, global_stats = runner.main(arg_dict)
    if len(result_list):
        results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
        print(f"\nResults:\n{results}")
        results.to_csv("results.tsv", sep="\t")
    else:
        logger.error("No results!")
    if len(fail_list):
        failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
        print(f"\nFailures:\n{failures}")
        failures.to_csv("failures.tsv", sep="\t")
    else:
        logger.info("No failures.")
    print(f"\nGlobal Stats:\n{global_stats}")
