"""
Analytics store (SQLite).

Append-only event log plus a small aggregates layer for the dashboard.
Absolutely no PII: rows key on anonymous session_id only.

Thread-safety: aiohttp runs single-threaded on the event loop, but the load
test hammers this from a thread pool, so we open with check_same_thread=False
and guard writes with a lock.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
import statistics
import threading
import time
from typing import Any, Dict, List, Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    session_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    data TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
"""


class Analytics:
    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.executescript(SCHEMA)
        self._db.commit()
        self._lock = threading.Lock()

    def record(self, session_id: str, kind: str,
               data: Optional[Dict[str, Any]] = None, ts: Optional[int] = None):
        ts = ts or int(time.time() * 1000)
        with self._lock:
            self._db.execute(
                "INSERT INTO events(ts, session_id, kind, data) VALUES (?,?,?,?)",
                (ts, session_id, kind, json.dumps(data or {})),
            )
            self._db.commit()

    # ---- queries -----------------------------------------------------------
    def _rows(self, sql: str, args=()) -> List[sqlite3.Row]:
        with self._lock:
            cur = self._db.execute(sql, args)
            return cur.fetchall()

    def count_by_kind(self) -> Dict[str, int]:
        rows = self._rows("SELECT kind, COUNT(*) c FROM events GROUP BY kind")
        return {r[0]: r[1] for r in rows}

    def latency_stats(self, kind: str) -> Dict[str, float]:
        rows = self._rows("SELECT data FROM events WHERE kind=?", (kind,))
        vals = []
        for (d,) in rows:
            try:
                v = json.loads(d).get("ms")
                if isinstance(v, (int, float)):
                    vals.append(v)
            except Exception:
                pass
        if not vals:
            return {}
        vals.sort()
        return {
            "n": len(vals),
            "min": round(min(vals), 1),
            "p50": round(statistics.median(vals), 1),
            "p95": round(vals[int(len(vals) * 0.95) - 1] if len(vals) > 1 else vals[0], 1),
            "max": round(max(vals), 1),
            "mean": round(statistics.mean(vals), 1),
        }

    def completion_stats(self) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT data FROM events WHERE kind='task_completion'")
        done = 0
        total = 0
        for (d,) in rows:
            total += 1
            try:
                if json.loads(d).get("completed"):
                    done += 1
            except Exception:
                pass
        pct = round(100 * done / total, 1) if total else 0.0
        return {"completed": done, "attempts": total, "pct": pct}

    def first_attempt_accuracy(self) -> Dict[str, Any]:
        rows = self._rows(
            "SELECT data FROM events WHERE kind='first_attempt_accuracy'")
        correct = 0
        total = 0
        for (d,) in rows:
            total += 1
            try:
                if json.loads(d).get("correct"):
                    correct += 1
            except Exception:
                pass
        pct = round(100 * correct / total, 1) if total else 0.0
        return {"correct": correct, "attempts": total, "pct": pct}

    def dashboard(self) -> Dict[str, Any]:
        return {
            "counts": self.count_by_kind(),
            "completion": self.completion_stats(),
            "first_attempt_accuracy": self.first_attempt_accuracy(),
            "latency": {
                "agent_command_latency": self.latency_stats("agent_command_latency"),
                "broadcast_latency": self.latency_stats("broadcast_latency"),
                "thumbnail_latency": self.latency_stats("thumbnail_latency"),
                "mode_transition_latency": self.latency_stats("mode_transition_latency"),
                "connect_duration": self.latency_stats("connect_duration"),
                "install_duration": self.latency_stats("install_duration"),
                "permission_duration": self.latency_stats("permission_duration"),
            },
        }

    # ---- exports -----------------------------------------------------------
    def export_json(self) -> str:
        rows = self._rows(
            "SELECT ts, session_id, kind, data FROM events ORDER BY id")
        out = [{"ts": r[0], "session_id": r[1], "kind": r[2],
                "data": json.loads(r[3] or "{}")} for r in rows]
        return json.dumps(out, indent=2)

    def export_csv(self) -> str:
        rows = self._rows(
            "SELECT ts, session_id, kind, data FROM events ORDER BY id")
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["ts", "session_id", "kind", "data"])
        for r in rows:
            w.writerow([r[0], r[1], r[2], r[3]])
        return buf.getvalue()
