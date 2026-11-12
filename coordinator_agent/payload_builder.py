"""(4) Chuẩn bị payload cho từng agent và (10) gói dữ liệu cho Reporting Agent."""
from __future__ import annotations

from .schema import (ConflictRecord, DeltaResult, DeltaSummary, ReportingPayload,
                     ScanContext, ScanStrategy, UnifiedFinding)

ORDER = {"new": 0, "persistent": 1, "resolved": 2}
SEV = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def build_reporting(ctx: ScanContext, findings: list[UnifiedFinding], conflicts: list[ConflictRecord],
                    delta: DeltaResult, strategy: ScanStrategy, drift_score: float,
                    warnings: list[str], errors: list[str]) -> ReportingPayload:
    findings = sorted(findings, key=lambda f: (ORDER.get(f.delta_status or "new", 3), SEV[f.severity]))
    return ReportingPayload(
        project_id=ctx.project_id,
        scan_id=ctx.scan_id,
        baseline_scan_id=delta.baseline_scan_id,
        findings=findings,
        conflicts=conflicts,
        delta_summary=DeltaSummary(new=len(delta.new), persistent=len(delta.persistent),
                                   resolved=len(delta.resolved)),
        drift_score=drift_score,
        strategy_proposal=strategy,
        warnings=warnings,
        errors=errors,
    )


def build_for(agent_name: str, strategy: ScanStrategy) -> dict:
    """Gợi ý đầu vào cho các agent ở lần quét sau (Orchestration sẽ chuyển tiếp)."""
    if agent_name == "code_analysis":
        return {"scope": strategy.scope, "target_modules": strategy.target_modules}
    if agent_name == "consistency_checking":
        return {"confidence_threshold": strategy.confidence_threshold,
                "target_modules": strategy.target_modules}
    raise ValueError(f"Không có payload cho agent '{agent_name}'")
