import os
from monitor import (
    get_system_metrics,
    get_processes,
    get_process_details,
    terminate_process,
    format_bytes,
    MetricsWorker,
)
from app import MainWindow, ProcessDetailsDialog, NumericTableWidgetItem
from PySide6.QtCore import Qt


def test_get_system_metrics():
    metrics = get_system_metrics()
    assert "cpu_percent" in metrics
    assert "ram_percent" in metrics
    assert "ram_used_gb" in metrics
    assert "ram_total_gb" in metrics
    assert "process_count" in metrics
    assert "processes" in metrics

    assert 0.0 <= metrics["cpu_percent"] <= 100.0
    assert 0.0 <= metrics["ram_percent"] <= 100.0
    assert metrics["ram_used_gb"] >= 0.0
    assert metrics["ram_total_gb"] > 0.0
    assert metrics["process_count"] > 0
    assert isinstance(metrics["processes"], list)


def test_get_processes():
    procs = get_processes()
    assert len(procs) > 0
    first = procs[0]
    for key in ["pid", "name", "user", "status", "cpu_percent", "memory_percent", "memory_mb"]:
        assert key in first


def test_get_process_details():
    current_pid = os.getpid()
    details = get_process_details(current_pid)
    assert details is not None
    assert details["pid"] == current_pid
    assert "name" in details
    assert "user" in details
    assert "status" in details
    assert "threads" in details
    assert "exe" in details
    assert "cmdline" in details

    # Non-existent PID should return None safely
    assert get_process_details(99999999) is None


def test_numeric_table_widget_item_sorting():
    item1 = NumericTableWidgetItem("5", 5)
    item2 = NumericTableWidgetItem("20", 20)
    assert item1 < item2
    assert not (item2 < item1)


def test_metrics_worker(qtbot):
    worker = MetricsWorker(interval=0.1)
    with qtbot.waitSignal(worker.metrics_updated, timeout=1000) as blocker:
        worker.start()

    assert blocker.signal_triggered
    metrics = blocker.args[0]
    assert "cpu_percent" in metrics
    assert "processes" in metrics
    worker.stop()


def test_main_window_dashboard_update(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    test_metrics = {
        "cpu_percent": 25.5,
        "ram_percent": 60.0,
        "ram_used_gb": 8.0,
        "ram_total_gb": 16.0,
        "process_count": 2,
        "processes": [],
    }

    window.update_metrics(test_metrics)

    assert window.cpu_label.text() == "25.5%"
    assert window.cpu_bar.value() == 25
    assert "60.0%" in window.ram_label.text()
    assert window.ram_bar.value() == 60
    assert window.proc_label.text() == "2"

    window.worker.stop()


def test_main_window_processes_and_filtering(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    mock_processes = [
        {"pid": 1, "name": "systemd", "user": "root", "status": "sleeping", "cpu_percent": 0.0, "memory_percent": 0.1, "memory_mb": 10.0},
        {"pid": 105, "name": "python_worker", "user": window.current_user, "status": "running", "cpu_percent": 5.2, "memory_percent": 1.2, "memory_mb": 50.0},
        {"pid": 300, "name": "db_service", "user": "postgres", "status": "sleeping", "cpu_percent": 1.0, "memory_percent": 2.5, "memory_mb": 120.0},
    ]

    test_metrics = {
        "cpu_percent": 10.0,
        "ram_percent": 40.0,
        "ram_used_gb": 4.0,
        "ram_total_gb": 16.0,
        "process_count": 3,
        "processes": mock_processes,
    }

    window.update_metrics(test_metrics)
    assert window.table.rowCount() == 3

    # Search by name
    window.search_input.setText("python")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "python_worker"

    # Search by PID
    window.search_input.setText("300")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "db_service"

    # Filter by status
    window.search_input.clear()
    window.status_combo.setCurrentText("running")
    assert window.table.rowCount() == 1
    assert window.table.item(0, 1).text() == "python_worker"

    # Filter by current user
    window.status_combo.setCurrentText("All Statuses")
    window.user_checkbox.setChecked(True)
    assert window.table.rowCount() == 1
    assert window.table.item(0, 2).text() == window.current_user

    window.worker.stop()


def test_process_details_dialog(qtbot):
    # Existing process dialog
    dialog = ProcessDetailsDialog(os.getpid())
    qtbot.addWidget(dialog)
    assert "Process Details" in dialog.windowTitle()

    # Missing process dialog handles gracefully
    missing_dialog = ProcessDetailsDialog(99999999)
    qtbot.addWidget(missing_dialog)
    assert missing_dialog.windowTitle() == "Process Details"


def test_terminate_process_success():
    from unittest.mock import patch, MagicMock
    with patch("monitor.psutil.Process") as mock_proc_cls:
        mock_instance = MagicMock()
        mock_instance.create_time.return_value = 12345.67
        mock_proc_cls.return_value = mock_instance

        success, msg = terminate_process(500, expected_create_time=12345.67)
        assert success is True
        assert "500" in msg
        mock_instance.terminate.assert_called_once()
        mock_instance.kill.assert_not_called()


def test_terminate_process_time_mismatch():
    from unittest.mock import patch, MagicMock
    with patch("monitor.psutil.Process") as mock_proc_cls:
        mock_instance = MagicMock()
        mock_instance.create_time.return_value = 99999.0
        mock_proc_cls.return_value = mock_instance

        success, msg = terminate_process(500, expected_create_time=12345.67)
        assert success is False
        assert "restarted" in msg
        mock_instance.terminate.assert_not_called()


def test_terminate_process_no_such_process():
    from unittest.mock import patch
    import psutil
    with patch("monitor.psutil.Process", side_effect=psutil.NoSuchProcess(500)):
        success, msg = terminate_process(500, expected_create_time=12345.67)
        assert success is False
        assert "no longer running" in msg


def test_terminate_process_access_denied():
    from unittest.mock import patch, MagicMock
    import psutil
    with patch("monitor.psutil.Process") as mock_proc_cls:
        mock_instance = MagicMock()
        mock_instance.create_time.return_value = 12345.67
        mock_instance.terminate.side_effect = psutil.AccessDenied(500)
        mock_proc_cls.return_value = mock_instance

        success, msg = terminate_process(500, expected_create_time=12345.67)
        assert success is False
        assert "Access denied" in msg


def test_main_window_terminate_flow(qtbot):
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow()
    qtbot.addWidget(window)

    window.latest_processes = [
        {"pid": 42, "name": "dummy_proc", "user": "test", "status": "running", "cpu_percent": 0.0, "memory_percent": 0.0, "memory_mb": 1.0, "create_time": 555.5}
    ]
    window.populate_processes()
    window.table.selectRow(0)

    # User cancels confirmation dialog
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No) as mock_q, \
         patch("app.terminate_process") as mock_term:
        window.terminate_selected_process()
        mock_term.assert_not_called()

    # User confirms termination
    with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes), \
         patch.object(QMessageBox, "information"), \
         patch("app.terminate_process", return_value=(True, "Process 42 terminated.")) as mock_term, \
         patch("app.get_processes", return_value=[]):
        window.terminate_selected_process()
        mock_term.assert_called_once_with(42, expected_create_time=555.5)
        assert window.table.rowCount() == 0

    window.worker.stop()


def test_main_window_terminate_no_selection(qtbot):
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow()
    qtbot.addWidget(window)
    window.table.clearSelection()

    with patch.object(QMessageBox, "information") as mock_info, \
         patch("app.terminate_process") as mock_term:
        window.terminate_selected_process()
        mock_info.assert_called_once()
        mock_term.assert_not_called()

    window.worker.stop()


def test_metrics_worker_records_only_tracked(tmp_path):
    from database import init_db, add_tracked_process, get_system_history, get_process_history
    db_file = str(tmp_path / "worker_test.db")
    init_db(db_file)

    # Track only PID 50, not PID 60
    add_tracked_process(50, "proc_50", 123.0, db_path=db_file)

    worker = MetricsWorker(interval=10.0, db_path=db_file)
    mock_metrics = {
        "cpu_percent": 15.0,
        "ram_percent": 45.0,
        "processes": [
            {"pid": 50, "name": "proc_50", "cpu_percent": 2.5, "memory_percent": 1.1, "create_time": 123.0},
            {"pid": 60, "name": "proc_60", "cpu_percent": 10.0, "memory_percent": 5.0, "create_time": 456.0},
        ],
    }

    worker._record(mock_metrics)

    sys_hist = get_system_history(0, db_path=db_file)
    assert len(sys_hist) == 1
    assert sys_hist[0]["cpu_percent"] == 15.0

    p50_hist = get_process_history(50, 0, db_path=db_file)
    assert len(p50_hist) == 1
    assert p50_hist[0]["cpu_percent"] == 2.5

    p60_hist = get_process_history(60, 0, db_path=db_file)
    assert len(p60_hist) == 0


def test_main_window_history_ui(qtbot):
    from unittest.mock import patch
    from PySide6.QtWidgets import QMessageBox

    window = MainWindow()
    qtbot.addWidget(window)
    initial_target_count = window.history_target_combo.count()

    window.latest_processes = [
        {"pid": 777, "name": "test_app", "user": "user", "status": "running", "cpu_percent": 3.0, "memory_percent": 1.5, "memory_mb": 20.0, "create_time": 100.0}
    ]
    window.populate_processes()
    window.table.selectRow(0)

    # Track process
    with patch.object(QMessageBox, "information"):
        window.toggle_track_selected_process()

    assert window.track_btn.text() == "Untrack"

    # Switch to History tab
    window.tabs.setCurrentIndex(2)
    assert window.history_target_combo.count() == initial_target_count + 1

    # Change time range
    window.history_range_combo.setCurrentIndex(1)
    assert window.history_range_combo.currentData() == 1800

    # Select tracked process in history target
    target_idx = window.history_target_combo.findData(777)
    assert target_idx >= 1
    window.history_target_combo.setCurrentIndex(target_idx)
    assert window.history_untrack_btn.isEnabled()

    # Untrack via history tab
    window.on_history_untrack_clicked()
    assert window.history_target_combo.count() == initial_target_count

    window.worker.stop()


def test_format_bytes():
    assert format_bytes(500) == "500 B"
    assert format_bytes(1536) == "1.5 KB"
    assert format_bytes(10 * 1024 * 1024) == "10.0 MB"
    assert format_bytes(int(2.5 * 1024 * 1024 * 1024)) == "2.5 GB"


def test_main_window_empty_filter_state(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window.latest_processes = [
        {"pid": 100, "name": "firefox", "user": "user", "status": "running", "cpu_percent": 1.0, "memory_percent": 2.0, "memory_mb": 50.0, "create_time": 10.0}
    ]
    window.populate_processes()
    assert window.table.rowCount() == 1

    # Filter by non-existent name
    window.search_input.setText("nonexistent_process_xyz_999")
    assert window.table.rowCount() == 0
    assert window.proc_count_label.text() == "No processes match the current filter"

    window.worker.stop()


def test_metrics_worker_prompt_shutdown(qtbot):
    import time
    worker = MetricsWorker(interval=10.0)
    worker.start()
    time.sleep(0.05)

    start_time = time.time()
    worker.stop()
    stop_duration = time.time() - start_time

    # Thread should stop promptly in < 0.5s rather than sleeping full 10s
    assert stop_duration < 0.5
    assert not worker.isRunning()




