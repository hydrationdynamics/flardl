"""Tests for server definition creation."""


from flardl import ServerDef

# module imports
from . import print_docstring


@print_docstring()
def test_server_def():
    """Create a single server definition."""
    a = ServerDef("aws", "s3.rcsb.org")
    assert a.name == "aws"
    assert str(a) == (
        "ServerDef(name='aws', server='s3.rcsb.org', server_dir='', "
        + "transport='https', transport_ver='1', bw_limit_mbps=0.0,"
        + " queue_depth=0, timeout_s=1000.0)"
    )

    assert a.get_all() == {
        "name": "aws",
        "server": "s3.rcsb.org",
        "server_dir": "",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_s": 1000.0,
    }
