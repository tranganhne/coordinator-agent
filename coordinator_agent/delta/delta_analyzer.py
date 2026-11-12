"""(8) Phân loại lỗi theo delta: Resolved / Persistent / New."""
from __future__ import annotations

from ..schema import DeltaResult, HistorySnapshot, ScanContext, UnifiedFinding


def _in_scope(f: UnifiedFinding, ctx: ScanContext) -> bool:
    """Finding có nằm trong phạm vi vừa quét không (chỉ ý nghĩa khi incremental)."""
    if ctx.scan_scope == "full":
        return True
    return f.location.source_component in set(ctx.scanned_modules)


def compare(current: list[UnifiedFinding], previous: HistorySnapshot,
            ctx: ScanContext) -> tuple[list[UnifiedFinding], list[UnifiedFinding], DeltaResult]:
    """So finding hiện tại với lần quét trước.

    Trả về:
      - all_findings: new + persistent + resolved (cho Reporting)
      - active: new + persistent (để ghi vào tầng unified của KB)
      - delta: danh sách fingerprint theo từng loại
    """
    prev = {f.fingerprint: f for f in previous.findings}
    cur = {f.fingerprint: f for f in current}
    delta = DeltaResult(baseline_scan_id=previous.scan_id)

    active: list[UnifiedFinding] = []
    for fp, f in cur.items():
        status = "persistent" if fp in prev else "new"
        getattr(delta, status).append(fp)
        active.append(f.model_copy(update={"delta_status": status, "not_rescanned": False}))

    resolved: list[UnifiedFinding] = []
    for fp, f in prev.items():
        if fp in cur:
            continue
        if _in_scope(f, ctx):
            delta.resolved.append(fp)
            resolved.append(f.model_copy(update={"delta_status": "resolved", "not_rescanned": False}))
        else:
            # Chưa được kiểm tra lại -> không được coi là đã sửa
            delta.persistent.append(fp)
            active.append(f.model_copy(update={"delta_status": "persistent", "not_rescanned": True}))

    return active + resolved, active, delta
