"""Tests for server definition creation."""


from flardl import ServerDef

# module imports
from . import print_docstring


@print_docstring()
def test_clean_datadir():
    """Create a single server definition."""
    a = ServerDef("aws", "s3.rcsb.org")
    assert a.name == "aws"
    assert str(a) == (
        "ServerDef(name='aws', server='s3.rcsb.org', dir='', "
        + "transport='https', transport_ver='1', bw_limit_mbps=0.0,"
        + " queue_depth=0, timeout_ms=0.0)"
    )

    assert a.get_all() == {
        "name": "aws",
        "server": "s3.rcsb.org",
        "dir": "",
        "transport": "https",
        "transport_ver": "1",
        "bw_limit_mbps": 0.0,
        "queue_depth": 0,
        "timeout_ms": 0.0,
    }
