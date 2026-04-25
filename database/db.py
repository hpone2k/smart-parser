import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "parsed_logs.db"

def get_connection():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parsed_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            filename TEXT,
            source_format TEXT,
            parsed_at TEXT,
            tool_id TEXT,
            timestamp TEXT,
            event_type TEXT,
            severity TEXT,
            parameters TEXT,
            alarms TEXT,
            summary TEXT,
            raw_snippet TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            filename TEXT,
            source_format TEXT,
            total_records INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_parsed_records(session_id: str, filename: str, source_format: str, records: list):
    conn = get_connection()
    now = datetime.utcnow().isoformat()
    conn.execute("""
        INSERT OR REPLACE INTO sessions (id, filename, source_format, total_records, created_at)
        VALUES (?, ?, ?, ?, ?)
    """, (session_id, filename, source_format, len(records), now))
    for r in records:
        conn.execute("""
            INSERT INTO parsed_logs
            (session_id, filename, source_format, parsed_at, tool_id, timestamp,
             event_type, severity, parameters, alarms, summary, raw_snippet)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, filename, source_format, now,
            r.get("tool_id", ""),
            r.get("timestamp", ""),
            r.get("event_type", ""),
            r.get("severity", ""),
            json.dumps(r.get("parameters", {})),
            json.dumps(r.get("alarms", [])),
            r.get("summary", ""),
            r.get("raw_snippet", "")[:500]
        ))
    conn.commit()
    conn.close()

def get_all_sessions():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM sessions ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_session_records(session_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM parsed_logs WHERE session_id = ? ORDER BY id",
        (session_id,)
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d["parameters"] = json.loads(d["parameters"] or "{}")
        d["alarms"] = json.loads(d["alarms"] or "[]")
        result.append(d)
    return result

def get_stats():
    conn = get_connection()
    total_sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_records = conn.execute("SELECT COUNT(*) FROM parsed_logs").fetchone()[0]
    formats = conn.execute(
        "SELECT source_format, COUNT(*) as cnt FROM sessions GROUP BY source_format"
    ).fetchall()
    conn.close()
    return {
        "total_sessions": total_sessions,
        "total_records": total_records,
        "formats": {r[0]: r[1] for r in formats}
    }
