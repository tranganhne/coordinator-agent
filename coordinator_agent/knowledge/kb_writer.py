"""(9) Ghi ngược vào KB - Coordinator là agent DUY NHẤT ghi tầng unified.

Ghi trong một transaction, kiểu upsert theo (project_id, scan_id):
chạy lại cùng một lần quét không sinh bản ghi trùng.
"""
from __future__ import annotations

import asyncio
import json

from ..schema import UnifiedRecord
from .db import connect


def _write(path: str, r: UnifiedRecord) -> None:
    conn = connect(path)
    try:
        with conn:  # transaction: lỗi giữa chừng thì rollback toàn bộ
            exists = conn.execute("SELECT seq FROM scan_index WHERE project_id=? AND scan_id=?",
                                  (r.project_id, r.scan_id)).fetchone()
            if exists:
                seq = exists[0]
            else:
                seq = (conn.execute("SELECT COALESCE(MAX(seq), 0) + 1 FROM scan_index").fetchone()[0])
            conn.execute(
                "INSERT OR REPLACE INTO scan_index(project_id, scan_id, commit_hash, status, seq) "
                "VALUES (?, ?, ?, 'completed', ?)",
                (r.project_id, r.scan_id, r.commit_hash, seq))
            conn.execute("DELETE FROM unified_findings WHERE scan_id=?", (r.scan_id,))
            conn.executemany(
                "INSERT INTO unified_findings(project_id, scan_id, fingerprint, data_json) VALUES (?, ?, ?, ?)",
                [(r.project_id, r.scan_id, f.fingerprint, f.model_dump_json()) for f in r.active_findings])
            conn.execute(
                "INSERT OR REPLACE INTO delta_results(project_id, scan_id, baseline_scan_id, data_json) "
                "VALUES (?, ?, ?, ?)",
                (r.project_id, r.scan_id, r.delta.baseline_scan_id, r.delta.model_dump_json()))
            conn.execute(
                "INSERT OR REPLACE INTO scan_strategies(project_id, scan_id, data_json) VALUES (?, ?, ?)",
                (r.project_id, r.scan_id, json.dumps(r.strategy.model_dump(), ensure_ascii=False)))
    finally:
        conn.close()


async def write_unified(path: str, record: UnifiedRecord) -> None:
    await asyncio.to_thread(_write, path, record)
