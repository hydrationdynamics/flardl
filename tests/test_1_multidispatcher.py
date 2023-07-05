"""Test multidispatcher function with mock downloader."""
from __future__ import annotations

import sys

import hypothesis.stateful as hypothesis_stateful

# third-party imports
import loguru
import pandas as pd
import pytest
from hypothesis import given
from hypothesis import register_random
from hypothesis import seed
from hypothesis import settings
from hypothesis import strategies as st

from flardl import INDEX_KEY
from flardl import MockDownloader
from flardl import MultiDispatcher
from flardl import zip_dict_to_indexed_list

from . import print_docstring
from . import stderr_format_func


ANYIO_BACKEND = "asyncio"


@pytest.fixture
def anyio_backend():
    """Select backend for testing."""
    return ANYIO_BACKEND


@pytest.mark.anyio
@settings(deadline=10000.0, derandomize=True)
@given(x=st.just(1))
async def test_anyio_multidispatcher(x) -> None:
    """Test multidispatcher."""
    n_items = 100
    n_consumers = 3
    max_retries = 2
    quiet = True
    arg_dict = {
        "code": [f"{i:04}" for i in range(n_items)],
        "file_type": "txt",
    }
    arg_list = zip_dict_to_indexed_list(arg_dict)
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=stderr_format_func)
    runner = MultiDispatcher(
        [
            MockDownloader(i, logger, quiet=quiet, write_file=True)
            for i in range(n_consumers)
        ],
        max_retries=max_retries,
        quiet=quiet,
    )
    result_list, fail_list, global_stats = await runner.run(arg_list)
    results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
    print(f"\nResults:\n{results}")
    results.to_csv("results.tsv", sep="\t")
    failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
    print(f"\nFailures:\n{failures}")
    print(f"\nGlobal Stats:\n{global_stats}")
