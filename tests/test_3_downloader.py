"""Test multidispatcher function with mock downloader."""

import sys
from pathlib import Path

# third-party imports
import loguru
import pandas as pd
import pytest

from flardl import INDEX_KEY
from flardl import MultiDispatcher

from . import SERVER_DEFS
from . import stderr_format_func


ANYIO_BACKEND = "asyncio"


@pytest.fixture
def anyio_backend():
    """Select backend for testing."""
    return ANYIO_BACKEND


URL_FILE = "filepaths.txt"


@pytest.mark.anyio
async def test_single_server_download(datadir_mgr) -> None:
    """Test download from a single server."""
    with datadir_mgr.in_tmp_dir(
        inpathlist=[URL_FILE],
        save_outputs=True,
        outscope="module",
    ):
        with Path(URL_FILE).open("r") as fp:
            paths = [line.strip() for line in fp]
        max_files = 5
        max_retries = 2
        quiet = False
        server_list = ["aws"]
        logger = loguru.logger
        logger.remove()
        logger.add(sys.stderr, format=stderr_format_func)
        runner = MultiDispatcher(
            SERVER_DEFS,
            worker_list=server_list,
            logger=logger,
            max_retries=max_retries,
            quiet=quiet,
            output_dir="./downloads",
            mock=False,
        )
        arg_dict = {
            "path": paths[:max_files],
            "out_filename": [p.split("/")[-1] for p in paths[:max_files]],
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
