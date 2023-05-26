"""Test multidispatcher function with mock downloader."""
from __future__ import annotations

import sys

# third-party imports
import loguru
import pandas as pd

from flardl import INDEX_KEY
from flardl import random_value_generator as rng
from flardl.mockdownloader import MockDownloader
from flardl.multidispatcher import MultiDispatcher

from . import print_docstring


NO_LEVEL_BELOW = 100


def _stderr_format_func(record: loguru.Record) -> str:
    """Do level-sensitive formatting."""
    if record["level"].no < NO_LEVEL_BELOW:
        return "<level>{message}</level>\n"
    return "<level>{level}</level>: <level>{message}</level>\n"


@print_docstring()
def test_multidispatcher():
    """Test multidispatcher."""
    n_items = 100
    n_consumers = 3
    max_retries = 2
    quiet = True
    arg_dict = {
        "int_arg": [i for i in range(n_items)],
        "str_arg": "blah",
        "float_arg": [
            round(rng.rng.uniform(low=1, high=10), 2) for i in range(n_items)
        ],
        "short_arg": [i + n_items for i in range(n_items - 1)],
    }
    logger = loguru.logger
    logger.remove()
    logger.add(sys.stderr, format=_stderr_format_func)
    runner = MultiDispatcher(
        [MockDownloader(i, logger, quiet=quiet) for i in range(n_consumers)],
        max_retries=max_retries,
        quiet=quiet,
    )
    result_list, fail_list, global_stats = runner.main(arg_dict)
    results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
    print(f"\nResults:\n{results}")
    results.to_csv("results.tsv", sep="\t")
    failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
    print(f"\nFailures:\n{failures}")
    print(f"\nGlobal Stats:\n{global_stats}")
