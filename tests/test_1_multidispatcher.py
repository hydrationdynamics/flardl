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
from flardl import MockDownloader
from flardl import MultiDispatcher
from flardl import zip_dict_to_indexed_list

from . import print_docstring
from . import stderr_format_func


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
    result_list, fail_list, global_stats = runner.main(arg_list, config="testing")
    results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
    print(f"\nResults:\n{results}")
    results.to_csv("results.tsv", sep="\t")
    failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
    print(f"\nFailures:\n{failures}")
    print(f"\nGlobal Stats:\n{global_stats}")
