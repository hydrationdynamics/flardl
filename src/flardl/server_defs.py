"""Define server attributes."""

from attrs import asdict
from attrs import define

from .common import SIMPLE_TYPES


DEFAULT_SET = "default"


@define
class ServerDef:
    """Class of derived statistics on numeric value."""

    name: str
    server: str
    server_dir: str = ""
    transport: str = "https"
    transport_ver: str = "1"
    bw_limit_mbps: float = 0.0
    queue_depth: int = 0
    timeout_s: float = 1000.0

    def get_all(self) -> dict[str, SIMPLE_TYPES]:
        """Return dictionary of non-private attributes."""
        return asdict(self, filter=lambda attr, value: not attr.name.startswith("_")) # noqa: ARG005
