"""Định danh ổn định cho một finding qua các lần quét."""
from __future__ import annotations

import hashlib

from ..schema import RawFinding


def normalize_path(path: str) -> str:
    """Đường dẫn tương đối, dùng dấu '/', bỏ './' ở đầu."""
    p = path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p.lstrip("/")


def fingerprint(f: RawFinding) -> str:
    """SHA-256 của rule_id + component nguồn + component đích + file.

    Không dùng số dòng vì số dòng thay đổi khi code bị sửa ở chỗ khác.
    """
    key = "|".join([
        f.rule_id.strip().lower(),
        f.source_component.strip().lower(),
        f.target_component.strip().lower(),
        normalize_path(f.file),
    ])
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
