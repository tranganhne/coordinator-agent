"""Hợp đồng dữ liệu (Data Contracts) của Coordinator Agent.

Mọi dữ liệu vào/ra đều đi qua các model Pydantic dưới đây để được kiểm tra kiểu.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Severity = Literal["low", "medium", "high", "critical"]
FindingType = Literal["forbidden_dependency", "missing_dependency", "divergence", "absence"]
Source = Literal["rule_engine", "graph_matching", "similarity"]
DeltaStatus = Literal["new", "persistent", "resolved"]


# ---------------------------------------------------------------- ĐẦU VÀO
class ScanContext(BaseModel):
    project_id: str
    scan_id: str
    commit_hash: str = ""
    scan_scope: Literal["full", "incremental"] = "full"
    scanned_modules: list[str] = Field(default_factory=list)
    baseline_scan_id: Optional[str] = None


class RawFinding(BaseModel):
    """Một nhận định do Consistency Checking Agent trả về."""
    id: str
    rule_id: str
    type: FindingType
    severity: str  # để str: normalizer sẽ chuẩn hóa về Severity
    source_component: str
    target_component: str
    file: str
    line: int = 0
    evidence: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    source: Source


class ConsistencyResult(BaseModel):
    drift_score: float = 0.0
    findings: list[dict] = Field(default_factory=list)  # validate từng phần tử sau
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class CoordinatorInput(BaseModel):
    context: ScanContext
    consistency_result: ConsistencyResult


# ---------------------------------------------------------------- XỬ LÝ
class Location(BaseModel):
    file: str
    line: int = 0
    source_component: str
    target_component: str


class Alternative(BaseModel):
    severity: str
    type: str
    source: str
    score: float


class UnifiedFinding(BaseModel):
    fingerprint: str
    rule_id: str
    type: FindingType
    severity: Severity
    confidence: float
    location: Location
    evidence: list[str] = Field(default_factory=list)
    delta_status: Optional[DeltaStatus] = None
    not_rescanned: bool = False
    conflict_resolved: bool = True
    alternatives: list[Alternative] = Field(default_factory=list)
    provenance: list[str] = Field(default_factory=list)


class ConflictValue(BaseModel):
    value: str
    source: str
    score: float


class ConflictRecord(BaseModel):
    fingerprint: str
    field: Literal["severity", "type"]
    values: list[ConflictValue]
    resolution: Literal["merged", "priority_by_reliability", "unresolved"]


class DeltaResult(BaseModel):
    baseline_scan_id: Optional[str] = None
    new: list[str] = Field(default_factory=list)
    persistent: list[str] = Field(default_factory=list)
    resolved: list[str] = Field(default_factory=list)


class ScanStrategy(BaseModel):
    scope: Literal["full", "incremental"] = "full"
    target_modules: list[str] = Field(default_factory=list)
    confidence_threshold: float = 0.7
    notes: list[str] = Field(default_factory=list)


class HistorySnapshot(BaseModel):
    scan_id: Optional[str] = None
    findings: list[UnifiedFinding] = Field(default_factory=list)


class ValidationReport(BaseModel):
    ok: bool
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------- ĐẦU RA
class DeltaSummary(BaseModel):
    new: int = 0
    persistent: int = 0
    resolved: int = 0


class ReportingPayload(BaseModel):
    """Gói dữ liệu gửi cho Reporting Agent (Nhiệm vụ 10)."""
    schema_version: str = "1.0.0"
    project_id: str
    scan_id: str
    baseline_scan_id: Optional[str] = None
    findings: list[UnifiedFinding]
    conflicts: list[ConflictRecord]
    delta_summary: DeltaSummary
    drift_score: float = 0.0
    strategy_proposal: ScanStrategy
    kb_persisted: bool = False
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class UnifiedRecord(BaseModel):
    """Bản ghi tầng unified của KB (Nhiệm vụ 9)."""
    project_id: str
    scan_id: str
    commit_hash: str = ""
    active_findings: list[UnifiedFinding]  # new + persistent (kể cả not_rescanned)
    delta: DeltaResult
    strategy: ScanStrategy
    current_count: int  # số finding quét được ở lần này (không tính not_rescanned)
    previous_count: int  # số finding còn mở ở baseline


class CoordinatorResult(BaseModel):
    reporting_payload: ReportingPayload
    validation: ValidationReport
    downstream_payloads: dict = Field(default_factory=dict)
