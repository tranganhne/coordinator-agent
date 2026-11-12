"""(5) Lưu trữ và tổng hợp kết quả trung gian theo scan_id.

Khi Orchestration chạy lại Consistency Checking trong cùng một lần quét,
các lô kết quả được gom thêm vào đây trước khi hoàn thiện.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any


class IntermediateStore:
    def __init__(self) -> None:
        self._data: dict[str, dict[str, list[Any]]] = defaultdict(lambda: defaultdict(list))

    def add(self, scan_id: str, step: str, value: Any) -> None:
        self._data[scan_id][step].append(value)

    def get(self, scan_id: str, step: str) -> list[Any]:
        return list(self._data.get(scan_id, {}).get(step, []))

    def all_batches(self, scan_id: str, step: str = "raw_findings") -> list[Any]:
        """Gộp phẳng mọi lô của một bước (ví dụ nhiều lô raw findings)."""
        out: list[Any] = []
        for batch in self.get(scan_id, step):
            out.extend(batch)
        return out

    def clear(self, scan_id: str) -> None:
        """Giải phóng sau khi ghi KB thành công."""
        self._data.pop(scan_id, None)
