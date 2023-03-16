"""Test QueueStats functionality."""
import sys

# third-party imports
import pandas as pd

from flardl import QueueStat
from flardl import QueueStats
from flardl import QueueWorkerStat

# module imports
from . import print_docstring


@print_docstring()
def test_queue_stats():
    """Test QueueStats functionality."""

    def diff(
        stop_time: float,
        start_time: float,
    ):
        difference = stop_time - start_time
        return difference

    def avg(non_global_history: list[float]):
        return sum(non_global_history) / float(non_global_history.maxlen)

    def worker_avg(work_history: list[float]):
        print("in worker_avg")
        return sum(work_history) / float(work_history.maxlen)

    # Test QueueStat class
    start_stat = QueueStat("start_time")
    start_stat.set(1.0)
    assert start_stat.get() == 1.0
    assert str(start_stat) == "1.0"
    counter_stat = QueueStat("counter", is_counter=True)
    assert counter_stat.get() == 0
    counter_stat.increment()
    assert counter_stat.get() == 1
    # test QueueWorkerStat class
    work_stat = QueueWorkerStat("work", history_size=4, totalize=True)
    work_stat.set(300.0, worker_name="worker0")
    work_stat.set(100.0, worker_name="worker1")
    return
    assert work_stat.get(worker_name="worker0") == 300.0
    assert work_stat.get() == 400.0
    assert str(work_stat) == "400.0"
    non_total_stat = QueueWorkerStat("non_total", totalize=False, propagate=False)
    non_total_stat.set(30, worker_name="worker0")
    non_total_stat.set(10, worker_name="worker1")
    assert non_total_stat.get(worker_name="worker0") == 30
    assert non_total_stat.get() is None
    # define some other possibilities of QueueStat and QueueWorkerStat
    stop_stat = QueueStat("stop_time")
    diff_stat = QueueStat("diff", diff)
    avg_stat = QueueStat("running_avg", avg)
    non_global_stat = QueueStat("non_global", is_global_stat=False, history_size=3)
    result_stat = QueueStat("result", is_result_stat=True)
    worker_avg_stat = QueueWorkerStat("worker_avg", worker_avg)
    # test QueueStats class get, set, and repr methods
    qs = QueueStats(
        stats=[
            start_stat,
            stop_stat,
            counter_stat,
            non_global_stat,
            result_stat,
            work_stat,
            non_total_stat,
            diff_stat,
            avg_stat,
        ]
    )
    qs["stop_time"].set(123.0)
    qs["counter"].increment(5)
    qs["non_global"].set(20)
    qs["result"].set(212)
    qs["non_total"].set(88)
    assert qs["result"].get() == 212
    assert str(qs["result"]) == "212"
    assert qs["counter"].get() == 6
    assert qs["work"].get(worker_name="worker0") == 300.0
    assert qs["work"].get() == 400.0
    assert str(qs) == (
        "{'start_time': 1.0, 'stop_time': 123.0,"
        + " 'counter': 6, 'non_global': 20, 'result': 212,"
        + " 'work': 400.0, 'non_total': 88, 'diff': None,"
        + " 'running_avg': None}"
    )
    # test update methods with no arguments
    qs.update()
    assert qs["diff"].get() == 122.0
    assert qs["running_avg"].get() is None
    assert qs.values(result_only=True) == {"result": 212}
    global_values = qs.values(global_only=True, worker_name="worker0")
    assert "non_global" not in global_values
    new_stat = QueueStat("new")
    # test update with arguments
    qs["non_global"].set(40)  # put in another of these to get up to minimum history
    qs.update(
        {
            "stop_time": 100.0,
            "start_time": 88.0,
            "work": 500.0,
            "non_global": 30,
            new_stat.name: new_stat,
        },
        worker_name="worker0",
    )
    assert qs["new"].get() is None
    assert qs["running_avg"].get() == 30.0
    # test deletes on qs
    del qs["non_global"]
    del qs["running_avg"]
    qs["new"].set(-92)
    assert qs.worker_stats() == {
        "total": {"work": 900.0, "non_total": 88},
        "worker0": {"work": 500.0, "non_total": 30},
        "worker1": {"work": 100.0, "non_total": 10},
    }
    # test per-worker history
    qs.update(
        {"work": 300.0, worker_avg_stat.name: worker_avg_stat}, worker_name="worker0"
    )

    assert qs["worker_avg"].get() is None
    assert qs["worker_avg"].get(worker_name="worker0") is None
    print(f"before update, worker avg value dict={qs['worker_avg'].value_dict}")
    qs.update()  # update the global to get the total worker average
    print(f"after update, worker avg value dict={qs['worker_avg'].value_dict}")
    assert qs["worker_avg"].get() == 300.0
    qs.update({"work": 400.0}, worker_name="worker0")
    print(f"after second update, worker avg value dict={qs['worker_avg'].value_dict}")
    assert qs["worker_avg"].get(worker_name="worker0") == 375.0
    print(qs.worker_stats())
    assert qs.worker_stats() == {
        "total": {"work": 1600.0, "non_total": 88, "worker_avg": 675.0},
        "worker0": {"work": 400.0, "non_total": 30, "worker_avg": 375.0},
        "worker1": {"work": 100.0, "non_total": 10},
    }
