"""Test Downloads."""

import logging
from pathlib import Path

# third-party imports
import pandas as pd
import pytest

from flardl import INDEX_KEY
from flardl import MultiDispatcher
from flardl import ServerDef

from . import print_docstring


ANYIO_BACKEND = "asyncio"
SERVER_DEFS = [
    ServerDef(
        "aws",
        "s3.rcsb.org",
        transport_ver="2",
        server_dir="pub/pdb/data",
    ),
    ServerDef(
        "us",
        "files.rcsb.org",
        server_dir="pub/pdb/data",
    ),
    ServerDef(
        "br",
        "bmrb.io",
        server_dir="ftp/pub/pdb/data",
    ),
    ServerDef(
        "uk",
        "ftp.ebi.ac.uk",
        server_dir="pub/databases/pdb/data",
    ),
    # ServerDef(
    #    "jp",
    #    "files.pdbj.org",
    #    server_dir="pub/pdb/data",
    # ),
]


@pytest.fixture()
def anyio_backend():
    """Select backend for testing."""
    return ANYIO_BACKEND


URL_FILE = "filepaths.txt"


@pytest.mark.anyio()
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
        server_list = ["aws"]
        runner = MultiDispatcher(
            SERVER_DEFS,
            worker_list=server_list,
            max_retries=max_retries,
            quiet=True,
            output_dir="./downloads",
            mock=False,
        )
        arg_dict = {
            "path": paths[:max_files],
            "out_filename": [p.split("/")[-1] for p in paths[:max_files]],
        }
        result_list, fail_list, global_stats = await runner.run(arg_dict)
        assert len(fail_list) == 0
        assert len(result_list) == max_files


@print_docstring()
def test_bad_url(datadir_mgr) -> None:
    """Test downloads with a bad url."""
    with datadir_mgr.in_tmp_dir(
        inpathlist=[URL_FILE],
        save_outputs=True,
        outscope="module",
    ):
        with Path(URL_FILE).open("r") as fp:
            paths = [line.strip() for line in fp]
        max_files = 5
        max_retries = 2
        runner = MultiDispatcher(
            SERVER_DEFS,
            max_retries=max_retries,
            quiet=True,
            output_dir="./downloads",
            mock=False,
        )
        arg_dict = {
            "path": paths[:max_files] + ["structures/all/mmCIF/xxxx.cif.gz"],
            "out_filename": [p.split("/")[-1] for p in paths[:max_files]]
            + ["imabadurl.txt"],
        }
        result_list, fail_list, global_stats = runner.main(arg_dict)
        assert len(fail_list) == 1
        assert len(result_list) == max_files


# @print_docstring()
# def test_bad_server_address(datadir_mgr) -> None:
#    """Test downloads with a failed server."""
#    with datadir_mgr.in_tmp_dir(
#        inpathlist=[URL_FILE],
#        save_outputs=True,
#        outscope="module",
#    ):
#        with Path(URL_FILE).open("r") as fp:
#            paths = [line.strip() for line in fp]
#        max_files = 10
#        max_retries = 2
#        bad_servers = SERVER_DEFS + [
#            ServerDef(
#                "bad",
#                "badserver.address",
#            ),
#        ]
#        runner = MultiDispatcher(
#            bad_servers,
#            max_retries=max_retries,
#            quiet=True,
#            output_dir="./downloads",
#            mock=False,
#        )
#        arg_dict = {
#            "path": paths[:max_files],
#            "out_filename": [p.split("/")[-1] for p in paths[:max_files]],
#        }
#        result_list, fail_list, global_stats = runner.main(arg_dict)
#        assert len(fail_list) == 0
#        assert len(result_list) == max_files


@print_docstring()
def test_production_download(datadir_mgr) -> None:
    """Test production downloads on a longish list."""
    with datadir_mgr.in_tmp_dir(
        inpathlist=[URL_FILE],
        save_outputs=True,
        outscope="module",
    ):
        with Path(URL_FILE).open("r") as fp:
            paths = [line.strip() for line in fp]
        max_files = -1
        max_retries = 2
        runner = MultiDispatcher(
            SERVER_DEFS,
            max_retries=max_retries,
            quiet=True,
            output_dir="./downloads",
            mock=False,
        )
        arg_dict = {
            "path": paths[:max_files],
            "out_filename": [p.split("/")[-1] for p in paths[:max_files]],
        }
        result_list, fail_list, global_stats = runner.main(arg_dict)
        if len(result_list):
            results = pd.DataFrame.from_dict(result_list).set_index(INDEX_KEY)
            print(f"\nResults:\n{results}")
            results.to_csv("results.tsv", sep="\t")
        else:
            logging.error("No results!")
        if len(fail_list):
            failures = pd.DataFrame.from_dict(fail_list).set_index(INDEX_KEY)
            print(f"\nFailures:\n{failures}")
            failures.to_csv("failures.tsv", sep="\t")
        else:
            logging.info("No failures.")
        print("\nGlobal Stats:")
        for key, value in global_stats.items():
            print(f"   {key}: {value}")
