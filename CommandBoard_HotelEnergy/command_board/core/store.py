"""Decision log, quality-decision log, dan audit trail (SQLite)."""
from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "command_board.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    role TEXT,
    owner TEXT,
    due_date TEXT,
    priority TEXT,
    status TEXT,           -- proposed / validated / monitor / rejected / closed
    action TEXT,
    note TEXT,
    validation_result TEXT,
    close_reason TEXT,
    severity TEXT,
    confidence TEXT,
    model_version TEXT,
    trust_status TEXT
);
CREATE TABLE IF NOT EXISTS quality_decisions (
    date TEXT PRIMARY KEY,
    decision TEXT NOT NULL,
    reason TEXT,
    role TEXT,
    ts TEXT
);
CREATE TABLE IF NOT EXISTS audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, role TEXT, entity TEXT, entity_id TEXT, action TEXT, detail TEXT
);
"""

STATUSES = ["proposed", "validated", "monitor", "rejected", "closed"]


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.executescript(SCHEMA)
    return c


def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def audit(role: str, entity: str, entity_id: str, action: str, detail: str = "") -> None:
    with _conn() as c:
        c.execute("INSERT INTO audit(ts, role, entity, entity_id, action, detail) VALUES (?,?,?,?,?,?)",
                  (now(), role, entity, entity_id, action, detail))


def get_quality_overrides() -> dict[str, str]:
    with _conn() as c:
        return dict(c.execute("SELECT date, decision FROM quality_decisions").fetchall())


def quality_decisions_df() -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql("SELECT * FROM quality_decisions ORDER BY date", c)


def set_quality_decision(date: str, decision: str, reason: str, role: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO quality_decisions(date, decision, reason, role, ts) VALUES (?,?,?,?,?) "
                  "ON CONFLICT(date) DO UPDATE SET decision=excluded.decision, reason=excluded.reason, "
                  "role=excluded.role, ts=excluded.ts", (date, decision, reason, role, now()))
    audit(role, "quality_decision", date, decision, reason)


def add_decision(**kw) -> int:
    kw.setdefault("created_at", now())
    kw.setdefault("updated_at", now())
    cols = ", ".join(kw)
    with _conn() as c:
        cur = c.execute(f"INSERT INTO decisions({cols}) VALUES ({', '.join('?' * len(kw))})", tuple(kw.values()))
        did = cur.lastrowid
    audit(kw.get("role", ""), "decision", str(did), "create",
          f"{kw.get('alert_date')} status={kw.get('status')} owner={kw.get('owner')}")
    return did


def update_decision(did: int, role: str, **kw) -> None:
    kw["updated_at"] = now()
    sets = ", ".join(f"{k}=?" for k in kw)
    with _conn() as c:
        c.execute(f"UPDATE decisions SET {sets} WHERE id=?", (*kw.values(), did))
    audit(role, "decision", str(did), "update", "; ".join(f"{k}={v}" for k, v in kw.items() if k != "updated_at"))


def decisions_df() -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql("SELECT * FROM decisions ORDER BY alert_date DESC, id DESC", c)


def audit_df() -> pd.DataFrame:
    with _conn() as c:
        return pd.read_sql("SELECT * FROM audit ORDER BY id DESC", c)


def latest_status_by_date() -> dict[str, str]:
    df = decisions_df()
    if df.empty:
        return {}
    return df.sort_values("id").groupby("alert_date")["status"].last().to_dict()


def reset_all(role: str) -> None:
    with _conn() as c:
        c.executescript("DELETE FROM decisions; DELETE FROM quality_decisions;")
    audit(role, "system", "-", "reset", "Decision & quality log dikosongkan (mode demo)")
