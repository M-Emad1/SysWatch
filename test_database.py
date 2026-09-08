import os
import time
import pytest
from database import (
    init_db,
    store_system_metric,
    store_process_metric,
    add_tracked_process,
    remove_tracked_process,
    get_tracked_processes,
    is_process_tracked,
    get_system_history,
    get_process_history,
)


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_metrics.db")
    init_db(db_file)
    return db_file


def test_init_db(temp_db):
    assert os.path.exists(temp_db)


def test_system_metric_storage_and_query(temp_db):
    t0 = 1000.0
    store_system_metric(t0, 15.0, 40.0, db_path=temp_db)
    store_system_metric(t0 + 10, 25.0, 42.0, db_path=temp_db)
    store_system_metric(t0 + 20, 35.0, 45.0, db_path=temp_db)

    # Query all
    history = get_system_history(t0, db_path=temp_db)
    assert len(history) == 3
    assert history[0]["cpu_percent"] == 15.0
    assert history[2]["cpu_percent"] == 35.0

    # Query since t0 + 15
    recent = get_system_history(t0 + 15, db_path=temp_db)
    assert len(recent) == 1
    assert recent[0]["cpu_percent"] == 35.0


def test_tracked_processes_management(temp_db):
    assert not is_process_tracked(101, db_path=temp_db)

    add_tracked_process(101, "proc_a", 500.0, db_path=temp_db)
    add_tracked_process(102, "proc_b", 600.0, db_path=temp_db)

    assert is_process_tracked(101, db_path=temp_db)
    assert is_process_tracked(102, db_path=temp_db)

    tracked = get_tracked_processes(db_path=temp_db)
    assert len(tracked) == 2
    assert tracked[0]["name"] == "proc_a"

    remove_tracked_process(101, db_path=temp_db)
    assert not is_process_tracked(101, db_path=temp_db)
    assert is_process_tracked(102, db_path=temp_db)
    assert len(get_tracked_processes(db_path=temp_db)) == 1


def test_process_metric_storage_and_query(temp_db):
    t0 = 2000.0
    store_process_metric(t0, 101, "proc_a", 1.5, 0.5, db_path=temp_db)
    store_process_metric(t0 + 5, 101, "proc_a", 2.0, 0.6, db_path=temp_db)
    store_process_metric(t0 + 5, 102, "proc_b", 10.0, 3.0, db_path=temp_db)

    # Query for 101
    p101_history = get_process_history(101, t0, db_path=temp_db)
    assert len(p101_history) == 2
    assert p101_history[0]["cpu_percent"] == 1.5
    assert p101_history[1]["cpu_percent"] == 2.0

    # Query for 102
    p102_history = get_process_history(102, t0, db_path=temp_db)
    assert len(p102_history) == 1
    assert p102_history[0]["memory_percent"] == 3.0

    # Query for non-existent PID
    p999_history = get_process_history(999, t0, db_path=temp_db)
    assert len(p999_history) == 0
