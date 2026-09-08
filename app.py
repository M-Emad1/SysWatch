import getpass
import sys
import time
from PySide6.QtCore import QDateTime, Qt
from PySide6.QtGui import QPainter
from PySide6.QtCharts import QChart, QChartView, QDateTimeAxis, QLineSeries, QValueAxis
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)
from database import (
    add_tracked_process,
    get_process_history,
    get_system_history,
    get_tracked_processes,
    init_db,
    is_process_tracked,
    remove_tracked_process,
)
from monitor import MetricsWorker, format_bytes, get_process_details, get_processes, terminate_process


class NumericTableWidgetItem(QTableWidgetItem):
    def __init__(self, text, sort_key):
        super().__init__(text)
        self.sort_key = sort_key

    def __lt__(self, other):
        if isinstance(other, NumericTableWidgetItem):
            return self.sort_key < other.sort_key
        return super().__lt__(other)


class ProcessDetailsDialog(QDialog):
    def __init__(self, pid, parent=None):
        super().__init__(parent)
        self.resize(520, 420)
        self.init_ui(pid)

    def init_ui(self, pid):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        details = get_process_details(pid)
        if not details:
            self.setWindowTitle("Process Details")
            msg = QLabel(f"Process {pid} is no longer running or access was denied.")
            msg.setStyleSheet("color: #d9534f; font-weight: bold; font-size: 13px;")
            layout.addWidget(msg)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)
            return

        self.setWindowTitle(f"Process Details - {details['name']} (PID: {details['pid']})")

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("PID:", QLabel(str(details["pid"])))
        form.addRow("Name:", QLabel(details["name"]))
        form.addRow("User:", QLabel(details["user"]))
        form.addRow("Status:", QLabel(details["status"]))
        form.addRow("CPU Usage:", QLabel(f"{details['cpu_percent']:.1f}%"))
        rss_str = format_bytes(details.get("memory_rss_bytes", int(details.get("memory_rss_mb", 0) * 1024 * 1024)))
        vms_str = format_bytes(details.get("memory_vms_bytes", int(details.get("memory_vms_mb", 0) * 1024 * 1024)))
        form.addRow(
            "Memory:",
            QLabel(f"{details['memory_percent']:.1f}% ({rss_str} RSS / {vms_str} VMS)"),
        )
        form.addRow("Threads:", QLabel(str(details["threads"])))
        form.addRow("Started At:", QLabel(details["started"]))

        exe_label = QLabel(details["exe"])
        exe_label.setWordWrap(True)
        form.addRow("Executable:", exe_label)
        layout.addLayout(form)

        cmd_title = QLabel("Command Line:")
        cmd_title.setStyleSheet("font-weight: bold;")
        layout.addWidget(cmd_title)

        cmd_edit = QTextEdit()
        cmd_edit.setPlainText(details["cmdline"])
        cmd_edit.setReadOnly(True)
        cmd_edit.setFixedHeight(75)
        layout.addWidget(cmd_edit)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Linux System Monitor")
        self.resize(850, 620)
        self.latest_processes = []
        self.current_user = getpass.getuser()

        init_db()
        self.init_ui()

        self.worker = MetricsWorker(interval=2.0)
        self.worker.metrics_updated.connect(self.update_metrics)
        self.worker.start()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)

        # Tab 1: Dashboard
        dashboard_widget = QWidget()
        dash_layout = QVBoxLayout(dashboard_widget)
        dash_layout.setContentsMargins(15, 15, 15, 15)
        dash_layout.setSpacing(12)

        title = QLabel("System Metrics")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        dash_layout.addWidget(title)

        # CPU Box
        cpu_box = QFrame()
        cpu_box.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; padding: 6px; }")
        cpu_layout = QVBoxLayout(cpu_box)
        cpu_header = QHBoxLayout()
        cpu_header.addWidget(QLabel("CPU Usage"))
        self.cpu_label = QLabel("0.0%")
        cpu_header.addWidget(self.cpu_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.cpu_bar = QProgressBar()
        self.cpu_bar.setRange(0, 100)
        self.cpu_bar.setTextVisible(False)
        cpu_layout.addLayout(cpu_header)
        cpu_layout.addWidget(self.cpu_bar)
        dash_layout.addWidget(cpu_box)

        # RAM Box
        ram_box = QFrame()
        ram_box.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; padding: 6px; }")
        ram_layout = QVBoxLayout(ram_box)
        ram_header = QHBoxLayout()
        ram_header.addWidget(QLabel("RAM Usage"))
        self.ram_label = QLabel("0.0% (0.0 / 0.0 GB)")
        ram_header.addWidget(self.ram_label, alignment=Qt.AlignmentFlag.AlignRight)
        self.ram_bar = QProgressBar()
        self.ram_bar.setRange(0, 100)
        self.ram_bar.setTextVisible(False)
        ram_layout.addLayout(ram_header)
        ram_layout.addWidget(self.ram_bar)
        dash_layout.addWidget(ram_box)

        # Processes Box
        proc_box = QFrame()
        proc_box.setStyleSheet("QFrame { border: 1px solid #444; border-radius: 6px; padding: 6px; }")
        proc_layout = QHBoxLayout(proc_box)
        proc_layout.addWidget(QLabel("Process Count"))
        self.proc_label = QLabel("0")
        self.proc_label.setStyleSheet("font-weight: bold;")
        proc_layout.addWidget(self.proc_label, alignment=Qt.AlignmentFlag.AlignRight)
        dash_layout.addWidget(proc_box)

        dash_layout.addStretch()

        dash_footer = QLabel("Refreshes automatically every 2 seconds")
        dash_footer.setStyleSheet("color: #888; font-size: 11px;")
        dash_footer.setAlignment(Qt.AlignmentFlag.AlignRight)
        dash_layout.addWidget(dash_footer)

        self.tabs.addTab(dashboard_widget, "Dashboard")

        # Tab 2: Processes
        proc_tab_widget = QWidget()
        proc_tab_layout = QVBoxLayout(proc_tab_widget)
        proc_tab_layout.setContentsMargins(10, 10, 10, 10)
        proc_tab_layout.setSpacing(10)

        # Filters Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search by name or PID...")
        self.search_input.textChanged.connect(self.apply_process_filter)
        filter_bar.addWidget(self.search_input, stretch=2)

        self.status_combo = QComboBox()
        self.status_combo.addItems(["All Statuses", "running", "sleeping", "idle", "stopped", "zombie"])
        self.status_combo.currentTextChanged.connect(self.apply_process_filter)
        filter_bar.addWidget(self.status_combo)

        self.user_checkbox = QCheckBox("Current User Only")
        self.user_checkbox.stateChanged.connect(self.apply_process_filter)
        filter_bar.addWidget(self.user_checkbox)

        self.details_btn = QPushButton("View Details")
        self.details_btn.clicked.connect(self.open_selected_process_details)
        filter_bar.addWidget(self.details_btn)

        self.track_btn = QPushButton("Track")
        self.track_btn.clicked.connect(self.toggle_track_selected_process)
        filter_bar.addWidget(self.track_btn)

        self.terminate_btn = QPushButton("Terminate")
        self.terminate_btn.setStyleSheet("color: #d9534f; font-weight: bold;")
        self.terminate_btn.clicked.connect(self.terminate_selected_process)
        filter_bar.addWidget(self.terminate_btn)

        proc_tab_layout.addLayout(filter_bar)

        # Processes Table
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["PID", "Name", "User", "Status", "CPU %", "Memory %", "Memory"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSortingEnabled(True)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.cellDoubleClicked.connect(self.on_table_double_clicked)
        self.table.itemSelectionChanged.connect(self.on_table_selection_changed)

        proc_tab_layout.addWidget(self.table)

        # Process footer
        proc_footer_layout = QHBoxLayout()
        self.proc_count_label = QLabel("Showing 0 processes")
        self.proc_count_label.setStyleSheet("color: #888; font-size: 11px;")
        proc_footer_layout.addWidget(self.proc_count_label)
        proc_footer_layout.addStretch()
        refresh_label = QLabel("Refreshes automatically every 2 seconds")
        refresh_label.setStyleSheet("color: #888; font-size: 11px;")
        proc_footer_layout.addWidget(refresh_label)
        proc_tab_layout.addLayout(proc_footer_layout)

        self.tabs.addTab(proc_tab_widget, "Processes")

        # Tab 3: History
        history_tab_widget = QWidget()
        history_layout = QVBoxLayout(history_tab_widget)
        history_layout.setContentsMargins(10, 10, 10, 10)
        history_layout.setSpacing(10)

        # History controls
        hist_controls = QHBoxLayout()
        hist_controls.addWidget(QLabel("Target:"))
        self.history_target_combo = QComboBox()
        self.history_target_combo.currentIndexChanged.connect(self.update_history_charts)
        hist_controls.addWidget(self.history_target_combo, stretch=2)

        hist_controls.addWidget(QLabel("Range:"))
        self.history_range_combo = QComboBox()
        self.history_range_combo.addItem("Last 5 Minutes", 300)
        self.history_range_combo.addItem("Last 30 Minutes", 1800)
        self.history_range_combo.addItem("Last 60 Minutes", 3600)
        self.history_range_combo.currentIndexChanged.connect(self.update_history_charts)
        hist_controls.addWidget(self.history_range_combo)

        self.history_untrack_btn = QPushButton("Untrack Process")
        self.history_untrack_btn.setEnabled(False)
        self.history_untrack_btn.clicked.connect(self.on_history_untrack_clicked)
        hist_controls.addWidget(self.history_untrack_btn)

        history_layout.addLayout(hist_controls)

        self.history_tip_label = QLabel("Tip: Select a process in the Processes tab and click 'Track' to graph its history.")
        self.history_tip_label.setStyleSheet("color: #888; font-size: 11px;")
        history_layout.addWidget(self.history_tip_label)

        # CPU Chart
        self.cpu_series = QLineSeries()
        self.cpu_series.setName("CPU %")
        self.cpu_chart = QChart()
        self.cpu_chart.addSeries(self.cpu_series)
        self.cpu_chart.setTitle("CPU Usage (%)")

        self.cpu_axis_x = QDateTimeAxis()
        self.cpu_axis_x.setFormat("HH:mm:ss")
        self.cpu_chart.addAxis(self.cpu_axis_x, Qt.AlignmentFlag.AlignBottom)
        self.cpu_series.attachAxis(self.cpu_axis_x)

        self.cpu_axis_y = QValueAxis()
        self.cpu_axis_y.setRange(0, 100)
        self.cpu_axis_y.setLabelFormat("%d%%")
        self.cpu_chart.addAxis(self.cpu_axis_y, Qt.AlignmentFlag.AlignLeft)
        self.cpu_series.attachAxis(self.cpu_axis_y)

        self.cpu_chart_view = QChartView(self.cpu_chart)
        self.cpu_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        history_layout.addWidget(self.cpu_chart_view)

        # RAM Chart
        self.ram_series = QLineSeries()
        self.ram_series.setName("RAM %")
        self.ram_chart = QChart()
        self.ram_chart.addSeries(self.ram_series)
        self.ram_chart.setTitle("RAM Usage (%)")

        self.ram_axis_x = QDateTimeAxis()
        self.ram_axis_x.setFormat("HH:mm:ss")
        self.ram_chart.addAxis(self.ram_axis_x, Qt.AlignmentFlag.AlignBottom)
        self.ram_series.attachAxis(self.ram_axis_x)

        self.ram_axis_y = QValueAxis()
        self.ram_axis_y.setRange(0, 100)
        self.ram_axis_y.setLabelFormat("%d%%")
        self.ram_chart.addAxis(self.ram_axis_y, Qt.AlignmentFlag.AlignLeft)
        self.ram_series.attachAxis(self.ram_axis_y)

        self.ram_chart_view = QChartView(self.ram_chart)
        self.ram_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        history_layout.addWidget(self.ram_chart_view)

        self.tabs.addTab(history_tab_widget, "History")
        self.refresh_history_targets()

    def on_tab_changed(self, index):
        if index == 1:
            self.populate_processes()
        elif index == 2:
            self.refresh_history_targets()
            self.update_history_charts()

    def update_metrics(self, metrics):
        cpu = metrics["cpu_percent"]
        ram = metrics["ram_percent"]
        ram_used = format_bytes(metrics.get("ram_used_bytes", metrics.get("ram_used_gb", 0) * (1024 ** 3)))
        ram_total = format_bytes(metrics.get("ram_total_bytes", metrics.get("ram_total_gb", 0) * (1024 ** 3)))
        procs = metrics["process_count"]

        self.cpu_label.setText(f"{cpu:.1f}%")
        self.cpu_bar.setValue(int(cpu))

        self.ram_label.setText(f"{ram:.1f}% ({ram_used} / {ram_total})")
        self.ram_bar.setValue(int(ram))

        self.proc_label.setText(str(procs))

        self.latest_processes = metrics.get("processes", [])

        if self.tabs.currentIndex() == 1 or self.table.rowCount() == 0:
            self.populate_processes()
        elif self.tabs.currentIndex() == 2:
            self.update_history_charts()

    def apply_process_filter(self):
        self.populate_processes()

    def populate_processes(self):
        search_query = self.search_input.text().strip().lower()
        status_filter = self.status_combo.currentText()
        user_only = self.user_checkbox.isChecked()
        tracked_pids = {tp["pid"] for tp in get_tracked_processes()}

        filtered = []
        for p in self.latest_processes:
            if search_query:
                pid_str = str(p["pid"])
                name_str = p["name"].lower()
                if search_query not in pid_str and search_query not in name_str:
                    continue

            if status_filter != "All Statuses" and p["status"].lower() != status_filter.lower():
                continue

            if user_only and p["user"] != self.current_user:
                continue

            filtered.append(p)

        selected_pid = None
        selected_items = self.table.selectedItems()
        if selected_items:
            selected_row = selected_items[0].row()
            pid_item = self.table.item(selected_row, 0)
            if pid_item and hasattr(pid_item, "sort_key"):
                selected_pid = pid_item.sort_key

        header = self.table.horizontalHeader()
        sort_col = header.sortIndicatorSection()
        sort_order = header.sortIndicatorOrder()

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))

        for row, p in enumerate(filtered):
            name_text = f"★ {p['name']}" if p["pid"] in tracked_pids else p["name"]
            mem_bytes = p.get("memory_bytes", int(p.get("memory_mb", 0) * 1024 * 1024))
            self.table.setItem(row, 0, NumericTableWidgetItem(str(p["pid"]), p["pid"]))
            self.table.setItem(row, 1, QTableWidgetItem(name_text))
            self.table.setItem(row, 2, QTableWidgetItem(p["user"]))
            self.table.setItem(row, 3, QTableWidgetItem(p["status"]))
            self.table.setItem(row, 4, NumericTableWidgetItem(f"{p['cpu_percent']:.1f}%", p["cpu_percent"]))
            self.table.setItem(row, 5, NumericTableWidgetItem(f"{p['memory_percent']:.1f}%", p["memory_percent"]))
            self.table.setItem(row, 6, NumericTableWidgetItem(format_bytes(mem_bytes), mem_bytes))

        self.table.setSortingEnabled(True)
        if sort_col >= 0:
            self.table.sortByColumn(sort_col, sort_order)

        if selected_pid is not None:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and getattr(item, "sort_key", None) == selected_pid:
                    self.table.selectRow(row)
                    break

        if not filtered and self.latest_processes:
            self.proc_count_label.setText("No processes match the current filter")
        else:
            self.proc_count_label.setText(f"Showing {len(filtered)} of {len(self.latest_processes)} processes")
        self.on_table_selection_changed()

    def on_table_selection_changed(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            self.track_btn.setText("Track")
            return
        selected_row = selected_items[0].row()
        pid_item = self.table.item(selected_row, 0)
        if pid_item and hasattr(pid_item, "sort_key"):
            self.track_btn.setText("Untrack" if is_process_tracked(pid_item.sort_key) else "Track")

    def toggle_track_selected_process(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a process from the table first.")
            return

        selected_row = selected_items[0].row()
        pid_item = self.table.item(selected_row, 0)
        if not pid_item or not hasattr(pid_item, "sort_key"):
            return

        pid = pid_item.sort_key
        proc = next((p for p in self.latest_processes if p["pid"] == pid), None)
        name = proc["name"] if proc else "Unknown"
        create_time = proc.get("create_time", 0.0) if proc else 0.0

        if is_process_tracked(pid):
            remove_tracked_process(pid)
            self.track_btn.setText("Track")
            QMessageBox.information(self, "Tracking", f"Stopped tracking process '{name}' (PID: {pid}).")
        else:
            add_tracked_process(pid, name, create_time)
            self.track_btn.setText("Untrack")
            QMessageBox.information(self, "Tracking", f"Now tracking process '{name}' (PID: {pid}).")

        self.refresh_history_targets()
        self.populate_processes()

    def refresh_history_targets(self):
        current_data = self.history_target_combo.currentData()
        self.history_target_combo.blockSignals(True)
        self.history_target_combo.clear()
        self.history_target_combo.addItem("System", None)

        tracked = get_tracked_processes()
        self.history_tip_label.setVisible(len(tracked) == 0)

        for tp in tracked:
            self.history_target_combo.addItem(f"{tp['name']} (PID: {tp['pid']})", tp["pid"])

        select_index = 0
        if current_data is not None:
            for i in range(self.history_target_combo.count()):
                if self.history_target_combo.itemData(i) == current_data:
                    select_index = i
                    break
        self.history_target_combo.setCurrentIndex(select_index)
        self.history_target_combo.blockSignals(False)

        self.history_untrack_btn.setEnabled(self.history_target_combo.currentData() is not None)

    def on_history_untrack_clicked(self):
        target_pid = self.history_target_combo.currentData()
        if target_pid is not None:
            remove_tracked_process(target_pid)
            self.refresh_history_targets()
            self.update_history_charts()
            self.populate_processes()

    def update_history_charts(self):
        target_pid = self.history_target_combo.currentData()
        self.history_untrack_btn.setEnabled(target_pid is not None)
        range_seconds = self.history_range_combo.currentData() or 300
        now = time.time()
        since = now - range_seconds

        if target_pid is None:
            history = get_system_history(since)
            cpu_points = [(h["timestamp"], h["cpu_percent"]) for h in history]
            ram_points = [(h["timestamp"], h["ram_percent"]) for h in history]
            suffix = " (no data yet)" if not history else ""
            self.cpu_chart.setTitle(f"System CPU Usage (%){suffix}")
            self.ram_chart.setTitle(f"System RAM Usage (%){suffix}")
        else:
            history = get_process_history(target_pid, since)
            cpu_points = [(h["timestamp"], h["cpu_percent"]) for h in history]
            ram_points = [(h["timestamp"], h["memory_percent"]) for h in history]
            title_name = self.history_target_combo.currentText()
            suffix = " (no data yet)" if not history else ""
            self.cpu_chart.setTitle(f"{title_name} - CPU Usage (%){suffix}")
            self.ram_chart.setTitle(f"{title_name} - Memory Usage (%){suffix}")

        self.cpu_series.clear()
        for ts, val in cpu_points:
            self.cpu_series.append(int(ts * 1000), val)

        self.ram_series.clear()
        for ts, val in ram_points:
            self.ram_series.append(int(ts * 1000), val)

        min_dt = QDateTime.fromMSecsSinceEpoch(int(since * 1000))
        max_dt = QDateTime.fromMSecsSinceEpoch(int(now * 1000))
        fmt = "HH:mm:ss" if range_seconds <= 300 else "HH:mm"

        self.cpu_axis_x.setFormat(fmt)
        self.cpu_axis_x.setRange(min_dt, max_dt)
        self.ram_axis_x.setFormat(fmt)
        self.ram_axis_x.setRange(min_dt, max_dt)

    def on_table_double_clicked(self, row, _column):
        pid_item = self.table.item(row, 0)
        if pid_item and hasattr(pid_item, "sort_key"):
            self.show_details_dialog(pid_item.sort_key)

    def open_selected_process_details(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a process from the table first.")
            return
        selected_row = selected_items[0].row()
        pid_item = self.table.item(selected_row, 0)
        if pid_item and hasattr(pid_item, "sort_key"):
            self.show_details_dialog(pid_item.sort_key)

    def show_details_dialog(self, pid):
        dialog = ProcessDetailsDialog(pid, self)
        dialog.exec()

    def terminate_selected_process(self):
        selected_items = self.table.selectedItems()
        if not selected_items:
            QMessageBox.information(self, "No Selection", "Please select a process to terminate.")
            return

        selected_row = selected_items[0].row()
        pid_item = self.table.item(selected_row, 0)
        if not pid_item or not hasattr(pid_item, "sort_key"):
            return

        pid = pid_item.sort_key
        proc = next((p for p in self.latest_processes if p["pid"] == pid), None)
        name = proc["name"] if proc else "Unknown"
        create_time = proc.get("create_time") if proc else None

        reply = QMessageBox.question(
            self,
            "Confirm Termination",
            f"Are you sure you want to terminate process '{name}' (PID: {pid})?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        success, msg = terminate_process(pid, expected_create_time=create_time)
        if success:
            QMessageBox.information(self, "Process Terminated", msg)
        else:
            QMessageBox.warning(self, "Termination Failed", msg)

        self.latest_processes = get_processes()
        self.populate_processes()

    def closeEvent(self, event):
        self.worker.stop()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
