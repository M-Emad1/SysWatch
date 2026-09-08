import datetime
import time
import psutil
from PySide6.QtCore import QThread, Signal
from database import (
    DEFAULT_DB_PATH,
    init_db,
    store_system_metric,
    store_process_metric,
    get_tracked_processes,
)


def format_bytes(bytes_count):
    if bytes_count < 1024:
        return f"{int(bytes_count)} B"
    elif bytes_count < 1024 ** 2:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 ** 3:
        return f"{bytes_count / (1024 ** 2):.1f} MB"
    else:
        return f"{bytes_count / (1024 ** 3):.1f} GB"


def get_processes():
    procs = []
    attrs = ["pid", "name", "username", "status", "cpu_percent", "memory_percent", "memory_info", "create_time"]
    for p in psutil.process_iter(attrs):
        try:
            info = p.info
            mem = info.get("memory_info")
            rss = mem.rss if mem else 0
            procs.append({
                "pid": info["pid"],
                "name": info.get("name") or "N/A",
                "user": info.get("username") or "N/A",
                "status": info.get("status") or "N/A",
                "cpu_percent": info.get("cpu_percent") or 0.0,
                "memory_percent": info.get("memory_percent") or 0.0,
                "memory_mb": rss / (1024 * 1024),
                "memory_bytes": rss,
                "create_time": info.get("create_time") or 0.0,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return procs


def terminate_process(pid, expected_create_time=None):
    try:
        p = psutil.Process(pid)
        if expected_create_time is not None:
            if abs(p.create_time() - expected_create_time) > 0.1:
                return False, f"Process {pid} has changed or restarted since it was selected."
        p.terminate()
        return True, f"Process {pid} terminated."
    except psutil.NoSuchProcess:
        return False, f"Process {pid} is no longer running."
    except psutil.AccessDenied:
        return False, f"Access denied: insufficient permissions to terminate process {pid}."
    except Exception as e:
        return False, f"Failed to terminate process {pid}: {e}"


def get_process_details(pid):
    try:
        p = psutil.Process(pid)
        with p.oneshot():
            mem = p.memory_info()
            try:
                exe = p.exe() or "N/A"
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                exe = "Access Denied"
            try:
                cmd = " ".join(p.cmdline()) or "N/A"
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                cmd = "Access Denied"

            rss = mem.rss if mem else 0
            vms = mem.vms if mem else 0
            return {
                "pid": p.pid,
                "name": p.name(),
                "user": p.username() if hasattr(p, "username") else "N/A",
                "status": p.status(),
                "cpu_percent": p.cpu_percent(),
                "memory_percent": p.memory_percent(),
                "memory_rss_bytes": rss,
                "memory_vms_bytes": vms,
                "memory_rss_mb": rss / (1024 * 1024),
                "memory_vms_mb": vms / (1024 * 1024),
                "threads": p.num_threads(),
                "started": datetime.datetime.fromtimestamp(p.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
                "exe": exe,
                "cmdline": cmd,
            }
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return None


def get_system_metrics():
    mem = psutil.virtual_memory()
    procs = get_processes()
    return {
        "cpu_percent": psutil.cpu_percent(interval=None),
        "ram_percent": mem.percent,
        "ram_used_bytes": mem.used,
        "ram_total_bytes": mem.total,
        "ram_used_gb": mem.used / (1024 ** 3),
        "ram_total_gb": mem.total / (1024 ** 3),
        "process_count": len(procs),
        "processes": procs,
    }


class MetricsWorker(QThread):
    metrics_updated = Signal(dict)

    def __init__(self, interval=2.0, db_path=DEFAULT_DB_PATH):
        super().__init__()
        self.interval = interval
        self.db_path = db_path
        self.running = True
        init_db(self.db_path)

    def run(self):
        psutil.cpu_percent(interval=None)
        metrics = get_system_metrics()
        self._record(metrics)
        self.metrics_updated.emit(metrics)

        while self.running:
            target_ms = int(self.interval * 1000)
            slept = 0
            while self.running and slept < target_ms:
                self.msleep(100)
                slept += 100
            if not self.running:
                break
            metrics = get_system_metrics()
            self._record(metrics)
            self.metrics_updated.emit(metrics)

    def _record(self, metrics):
        now = time.time()
        store_system_metric(now, metrics["cpu_percent"], metrics["ram_percent"], db_path=self.db_path)
        tracked = get_tracked_processes(db_path=self.db_path)
        if tracked:
            proc_map = {p["pid"]: p for p in metrics.get("processes", [])}
            for tp in tracked:
                p = proc_map.get(tp["pid"])
                if p and abs(p["create_time"] - tp["create_time"]) <= 0.1:
                    store_process_metric(
                        now,
                        tp["pid"],
                        tp["name"],
                        p["cpu_percent"],
                        p["memory_percent"],
                        db_path=self.db_path,
                    )

    def stop(self):
        self.running = False
        self.quit()
        self.wait(1000)
