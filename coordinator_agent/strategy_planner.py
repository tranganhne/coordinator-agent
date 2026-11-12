"""Pha Plan (MAPE-K): ĐỀ XUẤT chiến lược quét cho lần sau.

Coordinator chỉ đề xuất và lưu vào KB; việc áp dụng do Orchestration làm.
"""
from __future__ import annotations

from typing import Optional

from .config import Config
from .schema import ConflictRecord, ScanContext, ScanStrategy, UnifiedFinding


def propose_strategy(ctx: ScanContext, active: list[UnifiedFinding],
                     conflicts: list[ConflictRecord], previous: Optional[ScanStrategy],
                     cfg: Config) -> ScanStrategy:
    base = previous or ScanStrategy(scope=ctx.scan_scope, confidence_threshold=cfg.confidence_threshold)
    strategy = ScanStrategy(scope=base.scope, confidence_threshold=base.confidence_threshold)

    # R1: còn finding chưa được kiểm tra lại -> đưa module đó vào lần quét sau
    stale = sorted({f.location.source_component for f in active if f.not_rescanned})
    if stale:
        strategy.target_modules = stale
        strategy.notes.append(f"Quét lại các module chưa được kiểm tra: {', '.join(stale)}.")

    # R2: xung đột chưa hòa giải -> đề nghị người dùng rà soát
    unresolved = [c for c in conflicts if c.resolution == "unresolved"]
    if unresolved:
        strategy.notes.append(f"Có {len(unresolved)} xung đột chưa hòa giải, đề nghị người dùng rà soát.")

    # R3: quá nhiều finding có độ tin cậy thấp -> gợi ý kiểm tra lại
    if active:
        low = sum(1 for f in active if f.confidence < strategy.confidence_threshold)
        ratio = low / len(active)
        if ratio > cfg.low_confidence_ratio_alert:
            strategy.notes.append(f"{ratio:.0%} finding dưới ngưỡng tin cậy {strategy.confidence_threshold}; "
                                  "nên bật kiểm tra lại bằng LLM ở lần sau.")

    if not strategy.notes:
        strategy.notes.append("Không có bất thường, giữ nguyên chiến lược.")
    return strategy
