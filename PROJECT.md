# Linux System Monitor

A simple desktop system monitor for Linux built with Python, PySide6, psutil, SQLite, and pytest.

## Fixed Scope
- **Phase 1 (Completed)**:
  - Basic PySide6 desktop window.
  - Live dashboard displaying CPU usage (%), RAM usage (%), and total process count.
  - Background metrics collection via `QThread` (2-second refresh rate) to prevent UI blocking.
- **Phase 2 (Completed)**:
  - Processes page using QTableWidget.
  - Columns: PID, Name, User, Status, CPU %, Memory %, and Memory (MB).
  - Search by process name or PID.
  - Status filter and current user filter.
  - Column sorting (numeric-aware).
  - Process details dialog handling AccessDenied and terminated processes.
- **Phase 3 (Completed)**:
  - Safe process termination.
  - Confirmation dialog before termination.
  - Process verification via PID and creation time to avoid PID recycling race conditions.
  - Graceful handling of NoSuchProcess and AccessDenied without privilege escalation.
  - Immediate process list refresh after action.
- **Phase 4 (Completed)**:
  - Metric history storage via Python sqlite3 (no ORM).
  - Background recording of periodic system CPU and RAM samples.
  - User tracking of specific processes with storage limited strictly to tracked processes.
  - History page featuring CPU and RAM line charts using PySide6 QtCharts.
  - Time range selection: last 5, 30, and 60 minutes for system or tracked processes.
- **Subsequent Phases (Future)**:
  - Alert thresholds and notifications.

## Project Rules
- Keep the code simple and easy to read.
- No over-engineering, unnecessary abstractions, design patterns, or extra features.
- Use a small number of files and straightforward functions/classes.
- Avoid excessive comments and docstrings.
- Do not implement anything outside the requested phase.

## Tech Stack
- **Language**: Python 3
- **GUI Framework**: PySide6
- **System Metrics**: psutil
- **Database**: SQLite
- **Testing**: pytest
