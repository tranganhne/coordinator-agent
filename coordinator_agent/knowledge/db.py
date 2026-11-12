"""Kết nối SQLite và tạo bảng cho tầng unified của Kho tri thức (KB)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_index (
    project_id   TEXT NOT NULL,
    scan_id      TEXT NOT NULL,
    commit_hash  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    status       TEXT NOT NULL,
    seq          INTEGER NOT NULL,
    PRIMARY KEY (project_id, scan_id)
);
CREATE TABLE IF NOT EXISTS unified_findings (
    project_id  TEXT NOT NULL,
    scan_id     TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    data_json   TEXT NOT NULL,
    PRIMARY KEY (scan_id, fingerprint)
);
CREATE INDEX IF NOT EXISTS idx_uf_project ON unified_findings(project_id, fingerprint);
CREATE TABLE IF NOT EXISTS delta_results (
    project_id       TEXT NOT NULL,
    scan_id          TEXT PRIMARY KEY,
    baseline_scan_id TEXT,
    data_json        TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS scan_strategies (
    project_id TEXT PRIMARY KEY,
    scan_id    TEXT NOT NULL,
    data_json  TEXT NOT NULL
);
"""


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA)
    return conn
