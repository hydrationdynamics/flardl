"""Simple queue-associated statistical functions."""
from collections import UserDict
from collections import deque
from collections.abc import Iterable
from inspect import signature
from itertools import zip_longest
from typing import Any
from typing import Callable
from typing import Optional
from typing import TypeVar
from typing import Union


INDEX_KEY = "idx"
_GLOBAL_KEY = "total"
TIME_ROUNDING = 1  # digits, milliseconds
RATE_ROUNDING = 1  # digits, inverse seconds
TIME_EPSILON = 0.01  # milliseconds
SIMPLE_TYPES = Union[int, float, None]
SelfStats = TypeVar("SelfStats", bound="QueueStats")


class QueueStat:
    """Class for calculating stats on instrumented queues."""

    def __init__(
        self,
        name: str,
        label: Optional[str] = None,
        stat_func: Optional[Callable[[dict[str, SIMPLE_TYPES]], None]] = None,
        is_result_stat: bool = False,
        is_global_stat: bool = True,
        history_size: int = 0,
    ):
        """Initialize naming and storage."""
        self.name = name
        if label is not None:
            self.label = label
        else:
            self.label = name
        self.stat_func = stat_func
        if self.stat_func is not None:
            self.param_names = [p for p in signature(stat_func).parameters]  # type: ignore
        self.is_global_stat = is_global_stat
        self.is_result_stat = is_result_stat
        self.value: SIMPLE_TYPES = None
        self.history: deque[SIMPLE_TYPES] = deque(maxlen=history_size)

    def __repr__(self):
        """Represent string of self with values."""
        return str{self.value}

    def set(self, value: SIMPLE_TYPES, worker_name: Optional[str] = None) -> None:
        """Set value, with worker_name for convenience."""
        _unused = (worker_name,)  # noqa: F841
        self.value = value
        self.history.append(value)

    def get(self, worker_name: Optional[str] = None) -> SIMPLE_TYPES:
        """Get worker value, with work_name for convenience."""
        _unused = (worker_name,)  # noqa: F841
        return self.value

    def get_history(self, worker_name: Optional[str] = None) -> deque[SIMPLE_TYPES]:
        """Get the history of this quantity."""
        _unused = (worker_name,)  # noqa: F841
        return self.history

    def increment(self, addend: SIMPLE_TYPES = 1, worker_name: Optional[str] = None):
        """Increment the value, handling None."""
        if self.value is None:
            self.set(addend)
        else:
            if addend is not None:
                self.set(self.value + addend)

    def marshal_args(  # noqa: C901
        self, stat_dict: SelfStats, worker_name=None, worker_value=None
    ):
        """Marshal arguments for stat function from value dictionary."""
        args = []
        for arg_name in self.param_names:
            if arg_name == "value":
                args.append(self.value)
            elif arg_name == "worker_name":
                args.append(worker_name)
            elif arg_name == "worker_value":
                args.append(worker_value)
            else:
                if arg_name.endswith("_history"):
                    is_history = True
                    arg_name = arg_name[:-8]
                else:
                    is_history = False
                try:
                    if not is_history:
                        arg_val = stat_dict[arg_name].get(worker_name=worker_name)
                    else:
                        arg_val = stat_dict[arg_name].get_history(
                            worker_name=worker_name
                        )
                except KeyError as err:
                    if not is_history:
                        raise KeyError(arg_name + " not found.") from err
                    else:
                        raise KeyError(arg_name + " history not found.") from err
                if not is_history:
                    if arg_val is None:
                        raise ValueError(f"{arg_name} has not been set.") from None
                else:
                    if len(arg_val) < arg_val.maxlen:
                        raise ValueError(f"Not enough {arg_name} history.") from None
                args.append(arg_val)
        return args

    def update(
        self,
        stat_dict: SelfStats,
        worker_name: Optional[str] = None,
        worker_value: SIMPLE_TYPES = None,
    ):
        """Apply stat function, if defined, to update the value."""
        if self.stat_func is not None:
            print(f"in worker stat update {self.name} {self.stat_func}")
            try:
                args = self.marshal_args(
                    stat_dict, worker_name=worker_name, worker_value=worker_value
                )
            except ValueError as e:
                print(f"ValueError: {e}")
                return
            self.set(self.stat_func(*args))


class QueueWorkerStat(QueueStat):
    """Class for calculating stats on instrumented queues."""

    def __init__(
        self,
        name: str,
        stat_func: Optional[Callable[[dict[str, SIMPLE_TYPES]], None]] = None,
        is_result_stat: bool = False,
        is_global_stat: bool = True,
        history_size: int = 0,
        totalize: bool = True,
        propagate: bool = True,
    ):
        """Initialize naming and storage."""
        super().__init__(
            name,
            stat_func=stat_func,
            is_result_stat=is_result_stat,
            is_global_stat=is_global_stat,
            history_size=history_size,
        )
        if totalize:
            self.propagate = True
        else:
            self.propagate = propagate
        self.totalize = totalize
        self.value_dict: dict[str, SIMPLE_TYPES] = {}
        self.history_size = history_size
        self.history_dict: dict[str, deque[SIMPLE_TYPES]] = {}

    def __repr__(self, worker_name: Optional[str] = None):
        """String representation has values."""
        if worker_name is None:
            return super().__repr__()
        else:
            return str(self.get(worker_name=worker_name))

    def set(self, value: SIMPLE_TYPES, worker_name: Optional[str] = None) -> None:
        """Set value in worker/global store."""
        if worker_name is None:
            super().set(value)
        else:
            self.value_dict[worker_name] = value
            if worker_name not in self.history_dict:
                self.history_dict[worker_name] = deque(maxlen=self.history_size)
            self.history_dict[worker_name].append(value)
            if self.totalize:
                super().increment(value)
            elif self.propagate:
                super().set(value)

    def get(self, worker_name: Optional[str] = None) -> SIMPLE_TYPES:
        """Get value from worker store."""
        if worker_name is None:
            return self.value
        else:
            if worker_name not in self.value_dict:
                return None
            return self.value_dict[worker_name]

    def get_history(self, worker_name: Optional[str] = None) -> deque[SIMPLE_TYPES]:
        """Get value from worker store."""
        if worker_name is None:
            return self.history
        else:
            return self.history_dict[worker_name]

    def update(
        self,
        stat_dict: SelfStats,
        worker_name: Optional[str] = None,
        worker_value: SIMPLE_TYPES = None,
    ):
        """Update worker and global stat values."""
        _unused = (worker_value,)  # noqa: F841
        if worker_name is None:
            super().update(stat_dict)
            return
        if self.stat_func is not None:
            try:
                args = self.marshal_args(stat_dict, worker_name=worker_name)
            except ValueError:
                return
            self.set(self.stat_func(*args), worker_name=worker_name)
            newval = self.stat_func(*args)
            self.value_dict[worker_name] = newval
            if self.propagate:
                super().set(newval)
            elif self.totalize:
                super().increment(newval)
            else:
                super().update(stat_dict, worker_value=newval)

    def increment(self, addend: SIMPLE_TYPES = 1, worker_name: Optional[str] = None):
        """Increment worker and global stat values."""
        if worker_name is None:
            super().increment(addend)
        else:
            if worker_name not in self.value_dict:
                self.set(addend, worker_name=worker_name)
            else:
                current_value = self.get(worker_name=worker_name)
                if current_value is not None and addend is not None:
                    newval = current_value + addend
                    self.set(newval, worker_name=worker_name)
            if self.totalize:
                super().increment(addend)


class QueueStats(UserDict):
    """Dict-like class of queue stats."""

    def __init__(self, stats: list[QueueStat]):
        """Initialize dict of queue stats."""
        super().__init__({s.name: s for s in stats})

    def update_stats(self, *args, worker_name: Optional[str] = None) -> None:
        """Update using update methods in queue stats."""
        if len(args) > 0:
            input_dict = args[0].copy()
            pop_list = []
            for k, v in input_dict.items():
                if k not in self:
                    continue
                if not (isinstance(v, QueueStat) or isinstance(v, QueueWorkerStat)):
                    self[k].set(v, worker_name=worker_name)
                    pop_list.append(k)
            [input_dict.pop(k) for k in pop_list]
            super().update(input_dict)
        else:
            super().update(*args)
        [self[s].update(self, worker_name=worker_name) for s in self]

    def globals(self) -> dict[str, SIMPLE_TYPES]:
        """Return global stats."""
        ret_dict: dict[str, SIMPLE_TYPES] = {}
        for key in self:
            if not self[key].is_global_stat:
                continue
            ret_dict[key] = self[key].get()
        return ret_dict

    def results(
        self,
        worker_name: Optional[str] = None,
    ) -> dict[str, SIMPLE_TYPES]:
        """Return per-result stats."""
        ret_dict: dict[str, SIMPLE_TYPES] = {}
        for key in self:
            if not self[key].is_result_stat:
                continue
            ret_dict[key] = self[key].get(worker_name=worker_name)
        return ret_dict

    def worker_stats(self) -> dict[str, dict[str, SIMPLE_TYPES]]:
        """Return per-worker and global worker stats."""
        ret_dict: dict[str, dict[str, SIMPLE_TYPES]] = {_GLOBAL_KEY: {}}
        for key in self:
            if isinstance(self[key], QueueWorkerStat):
                for worker_name in self[key].value_dict:
                    if worker_name not in ret_dict:
                        ret_dict[worker_name] = {}
                    ret_dict[worker_name][key] = self[key].get(worker_name=worker_name)
                    if self[key].is_global_stat:
                        ret_dict[_GLOBAL_KEY][key] = self[key].get()
        return ret_dict
