# Linux System Monitor

A simple, fast, and responsive Linux desktop system monitor built with Python, PySide6, psutil, SQLite, and pytest.

---

## Features

- **Live Dashboard**: Real-time CPU usage, RAM utilization (percentage and human-readable used/total), and active process count, refreshed every 2 seconds via a non-blocking background thread (`QThread`).
- **Process Manager**:
  - Searchable process table displaying PID, Name, User, Status, CPU %, Memory %, and human-readable Memory size.
  - Instant text search by process name or PID.
  - Status filters (`running`, `sleeping`, `idle`, `stopped`, `zombie`) and "Current User Only" filter.
  - True numeric sorting on all columns (PID, CPU, Memory %, and Memory bytes).
  - Tracked process visual indicator (`★`).
- **Process Details**:
  - Detailed modal view showing PID, Name, User, Status, CPU %, Memory (RSS & VMS), Threads, Start Time, Executable Path, and full Command Line.
  - Gracefully handles processes that terminate or deny access.
- **Safe Process Termination**:
  - Confirmation dialog before termination.
  - Pre-flight verification comparing PID and process creation timestamp to protect against PID-recycling race conditions.
  - Sends `SIGTERM` (`terminate()`) rather than immediate `kill()`.
  - Never escalates privileges (`sudo` is blocked).
  - Clear error reporting for non-existent processes or insufficient permissions.
- **Metric History & Charts**:
  - Periodic CPU and RAM time-series metrics recorded to SQLite (WAL mode, zero ORM).
  - Selective tracking: stores historical metrics only for explicitly tracked processes to minimize storage and overhead.
  - Interactive line charts powered by `PySide6.QtCharts` (`QChart`, `QLineSeries`, `QDateTimeAxis`, `QValueAxis`).
  - Time ranges: Last 5 Minutes, Last 30 Minutes, and Last 60 Minutes for both System and Tracked Processes.
- **Polished UX & Responsiveness**:
  - Clean human-readable memory formatting (`B`, `KB`, `MB`, `GB`).
  - Responsive background worker shutdown using sliced sleep loops (< 100ms exit latency).
  - View-aware rendering: pauses heavy table repainting when inactive, maintaining low CPU overhead.
  - Helpful empty states for filtered queries and chart history.

---

## Architecture

The project follows a minimal, non-overengineered three-tier architecture:

```
┌────────────────────────────────────────────────────────┐
│                   app.py (PySide6 GUI)                 │
│  - MainWindow (Dashboard, Processes Table, History)    │
│  - ProcessDetailsDialog                                │
│  - NumericTableWidgetItem                              │
└───────────────────▲─────────────────▲──────────────────┘
                    │ Qt Signals      │ SQLite Queries
┌───────────────────┴──────────┐   ┌──┴──────────────────┐
│         monitor.py           │   │    database.py      │
│  - MetricsWorker (QThread)   │───▶  - SQLite direct    │
│  - psutil metrics collection │   │  - System history   │
│  - Safe termination          │   │  - Process history  │
│  - format_bytes helper       │   │  - Tracked procs    │
└──────────────────────────────┘   └─────────────────────┘
```

1. **GUI Layer (`app.py`)**: PySide6 interface with tabbed layout (`QTabWidget`), table management (`QTableWidget`), and charts (`QChartView`).
2. **Monitoring Layer (`monitor.py`)**: `MetricsWorker` thread polling `psutil` at 2s intervals; process inspection and safe `terminate()` execution.
3. **Database Layer (`database.py`)**: Direct `sqlite3` integration with WAL journal mode for concurrent thread safety without lock contention.

---

## Installation

### Prerequisites
- Linux OS (kernel 2.6+)
- Python 3.10+ (tested on Python 3.14)

### Setup Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running

Launch the desktop application:
```bash
.venv/bin/python app.py
```

---

## Testing

Run the full pytest suite:
```bash
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -v
```

The test suite covers:
- Metric extraction and human-readable byte formatting.
- Numeric sorting and table operations.
- Background worker thread signaling, tracking storage, and prompt shutdown.
- Safe termination flows (success, PID recycling mismatch, `NoSuchProcess`, `AccessDenied`, user cancel).
- Process filtering (name search, PID search, status, current user, empty filter states).
- SQLite storage and historical query ranges.

---

## Screenshots & Interface Layout

### 1. Dashboard Tab
```
+-------------------------------------------------------------+
| Linux System Monitor                                        |
+-------------------------------------------------------------+
| [ Dashboard ]  [ Processes ]  [ History ]                   |
|                                                             |
| System Metrics                                              |
| +---------------------------------------------------------+ |
| | CPU Usage                                         12.4% | |
| | [============-----------------------------------------] | |
| +---------------------------------------------------------+ |
| +---------------------------------------------------------+ |
| | RAM Usage                       52.1% (7.9 GB / 15.2 GB)| |
| | [=========================----------------------------] | |
| +---------------------------------------------------------+ |
| +---------------------------------------------------------+ |
| | Process Count                                       465 | |
| +---------------------------------------------------------+ |
|                               Refreshes every 2 seconds     |
+-------------------------------------------------------------+
```

### 2. Processes Tab
```
+-------------------------------------------------------------+
| [Search: bash...] [All Statuses v] [X] Current User         |
| [View Details] [Track] [Terminate]                          |
+-------------------------------------------------------------+
| PID   | Name         | User   | Status  | CPU % | Memory    |
|-------|--------------|--------|---------|-------|-----------|
| 1234  | ★ python     | user   | running | 3.2%  | 45.2 MB   |
| 5678  | bash         | user   | sleep   | 0.0%  | 12.0 MB   |
+-------------------------------------------------------------+
| Showing 2 of 465 processes        Refreshes every 2 seconds |
+-------------------------------------------------------------+
```

### 3. History Tab
```
+-------------------------------------------------------------+
| Target: [★ python (PID: 1234) v]  Range: [Last 5 Minutes v] |
| [Untrack Process]                                           |
+-------------------------------------------------------------+
| Python - CPU Usage (%)                                      |
| 100% |                                                      |
|   0% +-------------------------------------------------     |
|      14:10:00                 14:12:30             14:15:00 |
+-------------------------------------------------------------+
| Python - Memory Usage (%)                                   |
| 100% |                                                      |
|   0% +-------------------------------------------------     |
|      14:10:00                 14:12:30             14:15:00 |
+-------------------------------------------------------------+
```

---

## Limitations

- **Platform Specificity**: Designed for Linux environments relying on `/proc` filesystem metrics accessed via `psutil`.
- **Privilege Boundaries**: Only processes owned by the running user can be terminated. Unprivileged instances cannot kill root or other users' processes (privilege escalation is intentionally forbidden).
- **Transient Processes**: Processes that live for less than the 2-second collection cycle may not appear in the process table or historical charts.

---

## Project Structure

```
Linux_System_Monitor/
├── app.py              # Main GUI application & Qt widgets
├── monitor.py          # Metrics collection, MetricsWorker thread, termination logic
├── database.py         # SQLite persistence & query functions (no ORM)
├── test_monitor.py     # Unit and GUI tests for monitoring and UI flows
├── test_database.py    # Unit tests for SQLite storage and history queries
├── requirements.txt    # Project dependencies
├── PROJECT.md          # Project specification and phase progress
└── README.md           # Project documentation
```
