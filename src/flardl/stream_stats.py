"""Simple stream-associated statistical functions."""
from collections import UserDict
from collections import deque
from typing import Any
from typing import Optional
from typing import TypeVar
from typing import Union

from attrs import Attribute
from attrs import asdict
from attrs import define
from attrs import field

from .common import ALL
from .common import BYTES_TO_MEGABITS
from .common import DEFAULT_ROUNDING
from .common import HIST
from .common import MAX
from .common import NUMERIC_TYPE
from .common import RAVG
from .common import STAT_SUBLABELS
from .common import SUM
from .common import VALUE


# type definitions
OPTIONAL_NUMERIC = Optional[NUMERIC_TYPE]
OPTIONAL_NUMERIC_LIST = Union[OPTIONAL_NUMERIC, list[NUMERIC_TYPE]]

StreamStatsType = TypeVar("StreamStatsType", bound="StreamStats")
StatType = TypeVar("StatType", bound="Stat")
U = TypeVar("U")


def _nn(inst: Optional[U]) -> U:
    """Not-none helper to pass mypy."""
    assert inst is not None
    return inst


def _round(val: NUMERIC_TYPE, rounding: int) -> NUMERIC_TYPE:
    """Round with zero digits returning an int."""
    rounded_val = round(val, rounding)
    if rounding == 0:
        return int(rounded_val)
    return rounded_val


def _set_stat(instance: StatType, attrib: Attribute, val: NUMERIC_TYPE) -> NUMERIC_TYPE:
    """Round stat value and set derived quantities."""
    _unused = (attrib,)  # noqa: F841
    rounded_val = _round(val, instance._rounding)
    instance.n_obs += 1
    if instance.value is None:
        instance.min = rounded_val
        instance.max = rounded_val
        instance.sum = rounded_val
        instance.avg = rounded_val
    else:
        assert instance.min is not None
        instance.min = min(rounded_val, _nn(instance.min))
        instance.max = max(rounded_val, _nn(instance.max))
        instance.sum = _round(_nn(instance.sum) + rounded_val, instance._rounding)
        instance.avg = _round(_nn(instance.sum) / instance.n_obs, instance._rounding)
    instance._history.append(rounded_val)
    if instance._history_len > 0 and len(instance._history) == instance._history_len:
        instance.r_avg = _round(
            float(sum(instance._history)) / instance._history_len, instance._rounding
        )
    return rounded_val


@define
class Stat:
    """Class of derived statistics on numeric value."""

    _history_len: int = field(default=0, repr=False)
    _rounding: int = field(default=DEFAULT_ROUNDING, repr=False)
    value: OPTIONAL_NUMERIC = field(default=None, on_setattr=_set_stat)
    sum: OPTIONAL_NUMERIC = None
    n_obs: int = 0
    avg: OPTIONAL_NUMERIC = None
    min: OPTIONAL_NUMERIC = None
    max: OPTIONAL_NUMERIC = None
    _history: deque[NUMERIC_TYPE] = field(init=False, repr=False)
    r_avg: OPTIONAL_NUMERIC = None

    def __attrs_post_init__(self):
        """Initialize history after history length is set."""
        self._history = deque(maxlen=self._history_len)

    def get(self, key: str = VALUE) -> OPTIONAL_NUMERIC_LIST:
        """Return value of attribute."""
        if key is HIST:
            if self._history_len > 0 and len(self._history) == self._history_len:
                return list(self._history)
            else:
                return None
        return asdict(self, filter=lambda attr, value: not attr.name.startswith("_"))[
            key
        ]


class WorkerStat(UserDict):
    """Calculate stats on individual and all workers."""

    def __init__(
        self,
        label: str,
        workers: list[str],
        rounding: int = DEFAULT_ROUNDING,
        history_len: int = 0,
    ):
        """Initialize storage of stats."""
        self.label = label
        self.rounding = rounding
        self.history_len = history_len
        super().__init__()
        for worker in workers:
            self[worker] = Stat(rounding=self.rounding, history_len=self.history_len)

    def __repr__(self):
        """String of the overall stats."""
        return str(self[ALL])

    def set(
        self, value: NUMERIC_TYPE, worker: str = ALL, set_global: bool = True
    ) -> None:
        """Set value for a worker."""
        self[worker].value = value
        if worker is not ALL and set_global:
            self[ALL].value = value

    def get(
        self,
        key: str,
        /,
        default: Any = None,
        worker: str = ALL,
        scale: Optional[float] = None,
        rounding: Optional[int] = None,
    ) -> OPTIONAL_NUMERIC_LIST:
        """Get stat for a worker."""
        retval = self[worker].get(key)
        if scale is not None:
            retval *= scale
        if rounding is not None:
            retval = _round(retval, rounding)
        return retval


@define
class StatData:
    """Data class for WorkerStat initialization."""

    label: str
    rounding: int = DEFAULT_ROUNDING


@define
class ReportData:
    """Data class for report generation."""

    stat: str
    substat: str
    label: Optional[str] = None
    name: Optional[str] = None
    scale: Optional[float] = None
    rounding: Optional[int] = None


class StreamStats(UserDict):
    """Dictionary of per-worker queue stats with update calculations."""

    stat_data = {
        "retirement_t": StatData("retirement time, ms", rounding=2),
        "launch_t": StatData("launch time, ms", rounding=2),
        "service_t": StatData("service time, ns", rounding=2),
        "bytes": StatData("bytes downloaded", rounding=0),
        "dl_rate": StatData("per-file download rate, /s", rounding=1),
        "cum_rate": StatData("download rate, Mbit/s", rounding=0),
    }
    worker_stats = [
        ReportData(
            "retirement_t",
            VALUE,
            "Elapsed time, s",
            "elapsed_t",
            scale=1.0 / 1000.0,
            rounding=1,
        ),
        ReportData("dl_rate", MAX),
        ReportData(
            "bytes",
            SUM,
            scale=1 / 1024.0 / 1024.0,
            rounding=1,
            label="Total MB downloaded",
        ),
    ]
    file_stats = [
        ReportData("retirement_t", VALUE),
        ReportData("launch_t", VALUE),
        ReportData("service_t", VALUE),
        ReportData("bytes", VALUE),
    ]
    diagnostic_stats = [
        ReportData("dl_rate", RAVG),
    ]

    def __init__(self, workers: list[str], history_len: int):
        """Initialize dict of worker stats."""
        self.workers: list[str] = [ALL]
        if workers is not None:
            self.workers = workers + self.workers
        for report_list in [self.worker_stats, self.file_stats, self.diagnostic_stats]:
            for stat in report_list:
                if stat.name is None:
                    stat.name = stat.stat
                    if stat.substat != VALUE:
                        stat.name += "_" + stat.substat
                if stat.label is None:
                    stat.label = (
                        STAT_SUBLABELS[stat.substat] + self.stat_data[stat.stat].label
                    ).capitalize()
        super().__init__(
            {
                s: WorkerStat(
                    d.label,
                    workers=self.workers,
                    rounding=d.rounding,
                    history_len=history_len,
                )
                for s, d in self.stat_data.items()
            }
        )

    def update_stats(self, *args, worker: str = ALL) -> None:
        """Update using update methods in queue stats."""
        if len(args) > 0:
            input_dict = args[0].copy()
            pop_list = []
            for k, v in input_dict.items():
                if k not in self:
                    continue
                if not isinstance(v, WorkerStat):
                    self[k].set(v, worker=worker)
                    pop_list.append(k)
            [input_dict.pop(k) for k in pop_list]  # noqa: W0106
            super().update(input_dict)
        else:
            super().update(*args)
        self.calculate_updates(worker=worker)

    def globals(self) -> dict[str, OPTIONAL_NUMERIC]:
        """Return global stats."""
        ret_dict: dict[str, OPTIONAL_NUMERIC] = {}
        for key in self:
            if not self[key].is_global_stat:
                continue
            ret_dict[key] = self[key].get()
        return ret_dict

    def results(
        self,
        worker: str = ALL,
    ) -> dict[str, OPTIONAL_NUMERIC]:
        """Return per-result stats."""
        ret_dict: dict[str, OPTIONAL_NUMERIC] = {}
        for key in self:
            if not self[key].is_result_stat:
                continue
            ret_dict[key] = self[key].get(VALUE, worker=worker)
        return ret_dict

    def report_worker_stats(self) -> dict[str, dict[Optional[str], Any]]:
        """Return per-worker stats."""
        ret_dict = {}
        for worker in self.workers:
            ret_dict.update(
                {
                    worker: {
                        s.name: self[s.stat].get(
                            s.substat, worker=worker, scale=s.scale, rounding=s.rounding
                        )
                        for s in self.worker_stats
                    }
                }
            )
        return ret_dict

    def report_summary_stats(
        self, worker: str = ALL
    ) -> dict[Optional[str], OPTIONAL_NUMERIC]:
        """Return summary stats with nice labels for a worker."""
        return {
            s.label: self[s.stat].get(
                s.substat, worker=worker, scale=s.scale, rounding=s.rounding
            )
            for s in self.worker_stats
        }

    def report_file_stats(
        self, worker: str = ALL, diagnostics: bool = False
    ) -> dict[str, OPTIONAL_NUMERIC]:
        """Return file stats."""
        stat_list = self.file_stats
        if diagnostics:
            stat_list += self.diagnostic_stats
        return {
            _nn(s.name): self[s.stat].get(
                s.substat, worker=worker, scale=s.scale, rounding=s.rounding
            )
            for s in stat_list
        }

    def calculate_updates(
        self,
        worker: str = ALL,
    ):
        """Calculate all derived values."""
        # service_t
        try:
            self["service_t"].set(
                self["retirement_t"].get(VALUE, worker)
                - self["launch_t"].get(VALUE, worker),
                worker,
            )
        except TypeError:
            pass
        # dl_rate
        try:
            self["dl_rate"].set(
                self["bytes"].get(VALUE, worker)
                * 1000.0
                / 1024.0
                / 1024.0
                / self["service_t"].get(VALUE, worker),
                worker=worker,
                set_global=False,
            )
            # update global value
            self["dl_rate"].set(
                self["bytes"].get(VALUE)
                * 1000.0
                / 1024.0
                / 1024.0
                / self["service_t"].get(VALUE)
            )
        except TypeError:
            pass
        # cum_rate
        try:
            self["cum_rate"].set(
                self["bytes"].get(SUM, worker)
                * BYTES_TO_MEGABITS
                * 1000.0
                / self["retirement_t"].get(VALUE, worker),
                worker=worker,
                set_global=False,
            )
            # now update value for all workers
            self["cum_rate"].set(
                self["bytes"].get(SUM)
                * BYTES_TO_MEGABITS
                * 1000.0
                / self["retirement_t"].get(VALUE)
            )
        except TypeError:
            pass
