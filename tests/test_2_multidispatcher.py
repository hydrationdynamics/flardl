"""Test multidispatcher function with mock downloader."""

import sys

# third-party imports
import loguru
import pytest

from flardl import INDEX_KEY
from flardl import MultiDispatcher
from flardl import ServerDef

from . import print_docstring
from . import stderr_format_func


ANYIO_BACKEND = "asyncio"

SERVER_DEFS = [
    ServerDef(
        "aws",
        "s3.rcsb.org",
        dir="pub/pdb/data",
    ),
    ServerDef(
        "us",
        "files.rcsb.org",
        dir="pub/pdb/data",
    ),
    ServerDef(
        "br",
        "bmrb.io",
        dir="ftp/pub/pdb/data",
    ),
]


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
    server_list = ["aws", "us", "br"]
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
    n_failed = len(fail_list)
    assert n_failed == 3
    assert len(result_list) == n_items - n_failed


@print_docstring()
def test_production_multidispatcher() -> None:
    """Test multidispatcher using indeterminate event loop."""
    n_items = 100
    max_retries = 2
    quiet = True
    server_list = ["aws", "us", "br"]
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
    n_failed = len(fail_list)
    assert n_failed == 3
    assert len(result_list) == n_items - n_failed
