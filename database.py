import sqlite3

DEFAULT_DB_PATH = "metrics.db"


def get_db(db_path=DEFAULT_DB_PATH):
    conn = sqlite3.connect(db_path, timeout=10.0)
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS system_metrics (
                timestamp REAL NOT NULL,
                cpu_percent REAL NOT NULL,
                ram_percent REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_sys_time ON system_metrics(timestamp)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS process_metrics (
                timestamp REAL NOT NULL,
                pid INTEGER NOT NULL,
                name TEXT NOT NULL,
                cpu_percent REAL NOT NULL,
                memory_percent REAL NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_proc_time ON process_metrics(pid, timestamp)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracked_processes (
                pid INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                create_time REAL NOT NULL
            )
            """
        )


def store_system_metric(timestamp, cpu_percent, ram_percent, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO system_metrics (timestamp, cpu_percent, ram_percent) VALUES (?, ?, ?)",
            (timestamp, cpu_percent, ram_percent),
        )


def store_process_metric(timestamp, pid, name, cpu_percent, memory_percent, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT INTO process_metrics (timestamp, pid, name, cpu_percent, memory_percent) VALUES (?, ?, ?, ?, ?)",
            (timestamp, pid, name, cpu_percent, memory_percent),
        )


def add_tracked_process(pid, name, create_time, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO tracked_processes (pid, name, create_time) VALUES (?, ?, ?)",
            (pid, name, create_time),
        )


def remove_tracked_process(pid, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        conn.execute("DELETE FROM tracked_processes WHERE pid = ?", (pid,))


def get_tracked_processes(db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pid, name, create_time FROM tracked_processes ORDER BY name")
        return [{"pid": row[0], "name": row[1], "create_time": row[2]} for row in cursor.fetchall()]


def is_process_tracked(pid, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM tracked_processes WHERE pid = ?", (pid,))
        return cursor.fetchone() is not None


def get_system_history(since_timestamp, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, cpu_percent, ram_percent FROM system_metrics WHERE timestamp >= ? ORDER BY timestamp ASC",
            (since_timestamp,),
        )
        return [{"timestamp": row[0], "cpu_percent": row[1], "ram_percent": row[2]} for row in cursor.fetchall()]


def get_process_history(pid, since_timestamp, db_path=DEFAULT_DB_PATH):
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT timestamp, cpu_percent, memory_percent FROM process_metrics WHERE pid = ? AND timestamp >= ? ORDER BY timestamp ASC",
            (pid, since_timestamp),
        )
        return [{"timestamp": row[0], "cpu_percent": row[1], "memory_percent": row[2]} for row in cursor.fetchall()]
