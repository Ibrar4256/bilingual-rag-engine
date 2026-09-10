"""
In-memory ring buffer for recent log entries.

Loguru sink that captures the last N log messages so they can be
served to the admin UI via the /admin/logs endpoint.
"""

import threading
from collections import deque

_MAX_ENTRIES = 500
_buffer: deque[dict] = deque(maxlen=_MAX_ENTRIES)
_lock = threading.Lock()


def log_sink(message):
    record = message.record
    entry = {
        "timestamp": record["time"].strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "level": record["level"].name,
        "module": record["module"],
        "function": record["function"],
        "line": record["line"],
        "message": record["message"],
    }
    with _lock:
        _buffer.append(entry)


def get_recent_logs(limit: int = 100, level: str | None = None, search: str | None = None) -> list[dict]:
    with _lock:
        entries = list(_buffer)

    if level:
        level_upper = level.upper()
        entries = [e for e in entries if e["level"] == level_upper]

    if search:
        search_lower = search.lower()
        entries = [e for e in entries if search_lower in e["message"].lower()]

    return entries[-limit:]
