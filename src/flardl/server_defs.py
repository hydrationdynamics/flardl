"""Define server attributes."""
from typing import Optional

from attrs import asdict
from attrs import define

from .common import SIMPLE_TYPES


DEFAULT_SET = "default"


@define
class ServerDef:
    """Class of derived statistics on numeric value."""

    name: str
    server: str
    dir: str = ""
    transport: str = "https"
    transport_ver: str = "1"
    bw_limit_mbps: float = 0.0
    queue_depth: int = 0
    timeout_s: Optional[float] = None

    def get_all(self) -> dict[str, SIMPLE_TYPES]:
        """Return dictionary of non-private attributes."""
        return asdict(self, filter=lambda attr, value: not attr.name.startswith("_"))
