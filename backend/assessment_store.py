"""Local single-station records. SQLite keeps reports out of the Git repository."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


class AssessmentStore:
    def __init__(self, path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS assessments (id TEXT PRIMARY KEY, updated_at TEXT, data TEXT NOT NULL)")

    def save(self, state):
        if not state.get("session_id"):
            return
        with closing(sqlite3.connect(self.path)) as db, db:
            db.execute("INSERT OR REPLACE INTO assessments VALUES (?, ?, ?)", (state["session_id"], state["updated_at"], json.dumps(state, allow_nan=False)))

    def results(self, limit=100):
        with closing(sqlite3.connect(self.path)) as db, db:
            rows = db.execute("SELECT data FROM assessments ORDER BY updated_at DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(row[0]) for row in rows]

    def interrupt_active(self):
        # A restarted process cannot safely reuse a monotonic clock or stale hardware.
        for state in self.results():
            if state["phase"] not in ("ended", "interrupted"):
                state["phase"] = "interrupted"
                state["interruption_reason"] = "Backend restarted; start a new assessment. Recorded attempts were retained."
                self.save(state)
