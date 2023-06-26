"""Test queue stats functionality."""
from pytest import raises

from flardl import ALL
from flardl import AVG
from flardl import HIST
from flardl import MAX
from flardl import MIN
from flardl import NOBS
from flardl import RAVG
from flardl import SUM
from flardl import VALUE
from flardl.queue_stats import QueueStats
from flardl.queue_stats import WorkerStat

# module imports
from . import print_docstring


@print_docstring()
def test_worker_stat():
    """Test per-worker stat functionality."""
    pi_stat = WorkerStat("pi", [ALL], rounding=3, history_len=2)
    assert pi_stat.get(VALUE) is None
    # set first value
    pi_stat.set(3.14159)
    assert str(pi_stat) == (
        "Stat(value=3.142, sum=3.142, n_obs=1, avg=3.142,"
        + " min=3.142, max=3.142, r_avg=None)"
    )  # test __repr__
    assert pi_stat.get(VALUE) == 3.142
    assert pi_stat.get(MIN) == 3.142
    assert pi_stat.get(MAX) == 3.142
    assert pi_stat.get(SUM) == 3.142
    assert pi_stat.get(AVG) == 3.142
    assert pi_stat.get(NOBS) == 1
    assert pi_stat.get(RAVG) is None
    assert pi_stat.get(HIST) is None
    # second value
    pi_stat.set(-3.14159)
    assert pi_stat.get(VALUE) == -3.142
    assert pi_stat.get(MIN) == -3.142
    assert pi_stat.get(MAX) == 3.142
    assert pi_stat.get(SUM) == 0.0
    assert pi_stat.get(AVG) == 0.0
    assert pi_stat.get(NOBS) == 2
    assert pi_stat.get(RAVG) == 0.0
    assert [v for v in pi_stat.get(HIST)] == [3.142, -3.142]

    # third value, try an integer
    pi_stat.set(6)
    assert (
        str(pi_stat)
        == "Stat(value=6, sum=6.0, n_obs=3, avg=2.0, min=-3.142, max=6, r_avg=1.429)"
    )  # test __repr__
    assert pi_stat.get(VALUE) == 6
    assert [v for v in pi_stat.get(HIST)] == [-3.142, 6]
    assert pi_stat.get(RAVG) == 1.429
    # now try with per-worker stat
    bytes_stat = WorkerStat(
        "bytes in", ["worker0", "worker1", ALL], rounding=0, history_len=2
    )
    bytes_stat.set(100, worker="worker0")
    assert (
        str(bytes_stat)
        == "Stat(value=100, sum=100, n_obs=1, avg=100, min=100, max=100, r_avg=None)"
    )  # test __repr__
    bytes_stat.set(200, worker="worker1")
    assert (
        str(bytes_stat)
        == "Stat(value=200, sum=300, n_obs=2, avg=150, min=100, max=200, r_avg=150)"
    )  # test __repr__
    with raises(KeyError):
        bytes_stat.set(100, worker="worker2")
    # test global history values
    assert [v for v in bytes_stat.get(HIST)] == [100, 200]
    # test per-worker values
    assert bytes_stat.get(MIN, worker="worker0") == 100
    assert bytes_stat.get(MAX, worker="worker0") == 100
    assert bytes_stat.get(SUM, worker="worker0") == 100
    assert bytes_stat.get(AVG, worker="worker0") == 100
    assert bytes_stat.get(NOBS, worker="worker0") == 1
    assert bytes_stat.get(HIST, worker="worker0") is None
    assert bytes_stat.get(RAVG, worker="worker0") is None
    return


@print_docstring()
def test_queue_stats():
    """Test QueueStats functionality."""
    worker_list = ["worker0", "worker1"]
    qs = QueueStats(worker_list, history_len=2)
    qs.update_stats(
        {"retirement_t": 800.1, "launch_t": 0.1, "bytes": 2 * 1024 * 1024},
        worker="worker0",
    )
    initial_str = (
        "{'retirement_t': "
        + "Stat(value=800.1, sum=800.1, n_obs=1, avg=800.1, "
        + "min=800.1, max=800.1, r_avg=None),"
        + " 'launch_t': "
        + "Stat(value=0.1, sum=0.1, n_obs=1, avg=0.1, min=0.1, "
        + "max=0.1, r_avg=None),"
        + " 'service_t': "
        + "Stat(value=800.0, sum=800.0, n_obs=1, avg=800.0, min=800.0,"
        + " max=800.0, r_avg=None),"
        + " 'bytes': "
        + "Stat(value=2097152, sum=2097152, n_obs=1, avg=2097152, "
        + "min=2097152, max=2097152, r_avg=None),"
        + " 'dl_rate': "
        + "Stat(value=2.5, sum=2.5, n_obs=1, avg=2.5, min=2.5, max=2.5, r_avg=None),"
        + " 'cum_rate': "
        + "Stat(value=20, sum=20, n_obs=1, avg=20, min=20, max=20, r_avg=None)}"
    )
    assert str(qs) == initial_str
    assert str(qs["dl_rate"].get(VALUE, "worker0")) == "2.5"
    assert qs["cum_rate"].get(VALUE, "worker0") == 20
    qs.update_stats(
        {"retirement_t": 988.2, "launch_t": 100.2, "bytes": 1.5 * 1024 * 1024},
        worker="worker1",
    )
    assert qs.report_worker_stats() == {
        "worker0": {"elapsed_t": 0.8, "dl_rate_max": 2.5, "bytes_sum": 2.0},
        "worker1": {"elapsed_t": 1.0, "dl_rate_max": 1.7, "bytes_sum": 1.5},
        "all": {"elapsed_t": 1.0, "dl_rate_max": 2.5, "bytes_sum": 3.5},
    }
    assert qs.report_file_stats(worker="worker0") == {
        "retirement_t": 800.1,
        "launch_t": 0.1,
        "service_t": 800.0,
        "bytes": 2097152,
    }
    assert qs.report_file_stats(diagnostics=True, worker="worker0") == {
        "retirement_t": 800.1,
        "launch_t": 0.1,
        "service_t": 800.0,
        "bytes": 2097152,
        "dl_rate_r_avg": None,
    }
    assert qs.report_summary_stats(worker="worker0") == {
        "Elapsed time, s": 0.8,
        "Max per-file download rate, /s": 2.5,
        "Total MB downloaded": 2.0,
    }
    return
