"""(7) Đọc dữ liệu lịch sử từ tầng unified của KB."""
from __future__ import annotations

import asyncio
from typing import Optional

from ..schema import HistorySnapshot, ScanStrategy, UnifiedFinding
from .db import connect


def _load_previous(path: str, project_id: str, current_scan_id: str,
                   baseline_scan_id: Optional[str]) -> HistorySnapshot:
    conn = connect(path)
    try:
        if baseline_scan_id:
            row = conn.execute(
                "SELECT scan_id FROM scan_index WHERE project_id=? AND scan_id=? AND status='completed'",
                (project_id, baseline_scan_id)).fetchone()
        else:
            row = conn.execute(
                "SELECT scan_id FROM scan_index WHERE project_id=? AND scan_id<>? AND status='completed' "
                "ORDER BY seq DESC LIMIT 1",
                (project_id, current_scan_id)).fetchone()
        if not row:
            return HistorySnapshot()  # lần quét đầu tiên
        scan_id = row[0]
        rows = conn.execute("SELECT data_json FROM unified_findings WHERE scan_id=?", (scan_id,)).fetchall()
        return HistorySnapshot(scan_id=scan_id,
                               findings=[UnifiedFinding.model_validate_json(r[0]) for r in rows])
    finally:
        conn.close()


def _load_strategy(path: str, project_id: str) -> Optional[ScanStrategy]:
    conn = connect(path)
    try:
        row = conn.execute("SELECT data_json FROM scan_strategies WHERE project_id=?", (project_id,)).fetchone()
        return ScanStrategy.model_validate_json(row[0]) if row else None
    finally:
        conn.close()


def _scan_exists(path: str, project_id: str, scan_id: str) -> bool:
    conn = connect(path)
    try:
        return conn.execute("SELECT 1 FROM scan_index WHERE project_id=? AND scan_id=?",
                            (project_id, scan_id)).fetchone() is not None
    finally:
        conn.close()


async def load_previous(path: str, project_id: str, current_scan_id: str,
                        baseline_scan_id: Optional[str] = None) -> HistorySnapshot:
    return await asyncio.to_thread(_load_previous, path, project_id, current_scan_id, baseline_scan_id)


async def load_strategy(path: str, project_id: str) -> Optional[ScanStrategy]:
    return await asyncio.to_thread(_load_strategy, path, project_id)


def scan_exists(path: str, project_id: str, scan_id: str) -> bool:
    return _scan_exists(path, project_id, scan_id)
