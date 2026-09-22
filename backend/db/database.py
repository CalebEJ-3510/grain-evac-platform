"""
Database Layer: SQLite Local-First Persistence.
Creates and indexes tables:
- fused_state_records: indexed on (stack_id, ts)
- stacks: stack configuration, coordinates, precedence, vulnerability
- nodes: node hardware proxy, depth, health, battery
- alerts: log of escalated alerts, SMS dispatch records
- dispatch_overrides: supervisor queue overrides with audit codes
- config_versions: versioned weights, thresholds, and isotherm parameters
- node_maintenance_logs: audit logs for replacement and servicing actions
"""

from __future__ import annotations
import sqlite3
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "grain_evac.db"


def get_db_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initializes schema and indices."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Fused State Records
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS fused_state_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stack_id TEXT NOT NULL,
        ts TEXT NOT NULL,
        aw_max REAL NOT NULL,
        m_est REAL NOT NULL,
        dm_dt_24h REAL NOT NULL,
        t_core REAL NOT NULL,
        t_amb_ma24 REAL NOT NULL,
        mra REAL NOT NULL,
        r72 REAL NOT NULL,
        p_rain REAL NOT NULL,
        rhf REAL NOT NULL,
        mass_t REAL NOT NULL,
        age_d REAL NOT NULL,
        n_ok INTEGER NOT NULL,
        qflag TEXT NOT NULL,
        active_branch TEXT NOT NULL,
        vulnerability_score REAL NOT NULL,
        needs_inspection INTEGER NOT NULL,
        governing_node_id TEXT NOT NULL,
        raw_json TEXT
    );
    """)
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_fused_stack_ts ON fused_state_records (stack_id, ts);
    """)

    # 2. Stacks
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stacks (
        stack_id TEXT PRIMARY KEY,
        row_id TEXT NOT NULL,
        position_index INTEGER NOT NULL,
        tonnage_m REAL NOT NULL,
        formation_date TEXT NOT NULL,
        blocks_stack_id TEXT,
        blocked_by_stack_id TEXT,
        vulnerability_json TEXT NOT NULL,
        assigned_scenario TEXT NOT NULL,
        is_evacuated INTEGER DEFAULT 0,
        evacuated_at TEXT
    );
    """)

    # 3. Alerts Log
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        alert_id TEXT PRIMARY KEY,
        stack_id TEXT NOT NULL,
        band TEXT NOT NULL,
        triggered_at TEXT NOT NULL,
        reason_en TEXT NOT NULL,
        reason_ta TEXT NOT NULL,
        driving_node_ids TEXT NOT NULL,
        simulated_sms_sent INTEGER DEFAULT 0
    );
    """)

    # 4. Dispatch Overrides
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dispatch_overrides (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        stack_id TEXT NOT NULL,
        override_reason_code TEXT NOT NULL,
        supervisor_notes TEXT,
        overridden_at TEXT NOT NULL,
        original_rank INTEGER,
        new_rank INTEGER
    );
    """)

    # 5. Config Versions
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config_versions (
        version_id INTEGER PRIMARY KEY,
        timestamp TEXT NOT NULL,
        author TEXT NOT NULL,
        rationale TEXT NOT NULL,
        config_json TEXT NOT NULL
    );
    """)

    # 6. Maintenance Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS node_maintenance_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id TEXT NOT NULL,
        stack_id TEXT NOT NULL,
        action_type TEXT NOT NULL,  -- e.g. "REPLACE_BATTERY", "REPLACE_SENSOR", "INSPECT_LANCE"
        notes TEXT,
        logged_at TEXT NOT NULL,
        operator_role TEXT NOT NULL
    );
    """)

    conn.commit()
    conn.close()


def save_fused_record(record_dict: Dict[str, Any]) -> None:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO fused_state_records (
        stack_id, ts, aw_max, m_est, dm_dt_24h, t_core, t_amb_ma24, mra,
        r72, p_rain, rhf, mass_t, age_d, n_ok, qflag, active_branch,
        vulnerability_score, needs_inspection, governing_node_id, raw_json
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        record_dict["stack_id"],
        record_dict["ts"].isoformat() if hasattr(record_dict["ts"], "isoformat") else str(record_dict["ts"]),
        record_dict["aw_max"],
        record_dict["m_est"],
        record_dict["dm_dt_24h"],
        record_dict["t_core"],
        record_dict["t_amb_ma24"],
        record_dict["mra"],
        record_dict["r72"],
        record_dict["p_rain"],
        record_dict["rhf"],
        record_dict["mass_t"],
        record_dict["age_d"],
        record_dict["n_ok"],
        record_dict["qflag"],
        record_dict["active_branch"],
        record_dict["vulnerability_score"],
        1 if record_dict.get("needs_inspection") else 0,
        record_dict["governing_node_id"],
        json.dumps(record_dict, default=str),
    ))
    conn.commit()
    conn.close()


def get_stack_history(stack_id: str, limit: int = 200) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM fused_state_records
    WHERE stack_id = ?
    ORDER BY ts ASC
    LIMIT ?;
    """, (stack_id, limit))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]
