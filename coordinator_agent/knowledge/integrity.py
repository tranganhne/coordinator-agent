"""(6) Kiểm tra toàn vẹn dữ liệu trước khi ghi vào KB."""
from __future__ import annotations

from ..schema import UnifiedRecord, ValidationReport
from .kb_reader import scan_exists


def validate(record: UnifiedRecord, kb_path: str) -> ValidationReport:
    errors: list[str] = []
    d = record.delta

    # 1. Fingerprint không trùng trong cùng một lần quét
    fps = [f.fingerprint for f in record.active_findings]
    if len(fps) != len(set(fps)):
        errors.append("Có fingerprint bị trùng trong cùng một lần quét.")

    # 2. Baseline phải tồn tại và khác lần quét hiện tại
    if d.baseline_scan_id:
        if d.baseline_scan_id == record.scan_id:
            errors.append("baseline_scan_id trùng với scan_id hiện tại.")
        elif not scan_exists(kb_path, record.project_id, d.baseline_scan_id):
            errors.append(f"baseline_scan_id '{d.baseline_scan_id}' không tồn tại trong KB "
                          f"của project '{record.project_id}'.")

    # 3. Số liệu phải khớp
    not_rescanned = sum(1 for f in record.active_findings if f.not_rescanned)
    if record.current_count != len(d.new) + len(d.persistent) - not_rescanned:
        errors.append("Số finding lần này != New + Persistent (không tính not_rescanned).")
    if record.previous_count != len(d.resolved) + len(d.persistent):
        errors.append("Số finding lần trước != Resolved + Persistent.")

    # 4. Mọi fingerprint trong delta (trừ resolved) phải có trong active_findings
    active = set(fps)
    missing = [fp for fp in d.new + d.persistent if fp not in active]
    if missing:
        errors.append(f"{len(missing)} fingerprint trong delta không có trong active_findings.")

    return ValidationReport(ok=not errors, errors=errors)
