"""(3) Chuẩn hóa schema: đưa mọi finding về một định dạng chung."""
from __future__ import annotations

from ..config import Config
from ..delta.fingerprint import normalize_path
from ..schema import RawFinding

VALID_SEVERITIES = {"low", "medium", "high", "critical"}


def normalize_raw(f: RawFinding, cfg: Config) -> RawFinding:
    """Chuẩn hóa một RawFinding trước khi gom nhóm.

    - severity về 4 mức chuẩn (dùng severity_aliases)
    - đường dẫn file tương đối, dấu '/'
    - confidence làm tròn 2 chữ số
    Ném ValueError nếu severity không nhận ra được.
    """
    sev = f.severity.strip().lower()
    sev = cfg.severity_aliases.get(sev, sev)
    if sev not in VALID_SEVERITIES:
        raise ValueError(f"severity không hợp lệ: {f.severity!r}")
    return f.model_copy(update={
        "severity": sev,
        "file": normalize_path(f.file),
        "source_component": f.source_component.strip(),
        "target_component": f.target_component.strip(),
        "confidence": round(f.confidence, 2),
    })
