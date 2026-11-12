"""(2) Phát hiện và xử lý xung đột giữa các nguồn trong cùng một nhóm finding.

Mỗi finding được chấm điểm: score = reliability[source] x confidence.
  - Các nguồn báo giống nhau            -> merge, conflict_resolved = True
  - Khác nhau, chênh lệch điểm >= eps   -> ưu tiên bên điểm cao, True
  - Khác nhau, chênh lệch điểm <  eps   -> giữ cả hai (alternatives), False
"""
from __future__ import annotations

from ..config import Config
from ..schema import (Alternative, ConflictRecord, ConflictValue, Location,
                      RawFinding, UnifiedFinding)

FIELDS = ("severity", "type")


def _score(f: RawFinding, cfg: Config) -> float:
    return round(cfg.source_reliability.get(f.source, 0.5) * f.confidence, 4)


def resolve(fp: str, group: list[RawFinding], cfg: Config) -> tuple[UnifiedFinding, list[ConflictRecord]]:
    scored = [(f, _score(f, cfg)) for f in group]
    # Bên thắng = điểm cao nhất (nếu bằng nhau, giữ thứ tự xuất hiện)
    winner, _ = max(scored, key=lambda x: x[1])

    records: list[ConflictRecord] = []
    all_resolved = True

    for fld in FIELDS:
        # điểm cao nhất của mỗi giá trị khác nhau
        best: dict[str, tuple[float, str]] = {}
        for f, s in scored:
            v = getattr(f, fld)
            if v not in best or s > best[v][0]:
                best[v] = (s, f.source)
        if len(best) < 2:
            continue
        ranked = sorted(best.items(), key=lambda kv: kv[1][0], reverse=True)
        gap = ranked[0][1][0] - ranked[1][1][0]
        resolved = gap >= cfg.conflict_epsilon
        all_resolved = all_resolved and resolved
        records.append(ConflictRecord(
            fingerprint=fp,
            field=fld,
            values=[ConflictValue(value=v, source=src, score=s) for v, (s, src) in ranked],
            resolution="priority_by_reliability" if resolved else "unresolved",
        ))

    has_conflict = bool(records)
    if len(group) > 1 and not has_conflict:
        # Nhiều nguồn báo giống hệt nhau -> merge
        records.append(ConflictRecord(
            fingerprint=fp, field="severity",
            values=[ConflictValue(value=f.severity, source=f.source, score=s) for f, s in scored],
            resolution="merged",
        ))

    alternatives = [
        Alternative(severity=f.severity, type=f.type, source=f.source, score=s)
        for f, s in scored
        if f is not winner and (f.severity != winner.severity or f.type != winner.type)
    ]

    evidence: list[str] = []
    for f, _ in scored:
        if f.evidence and f.evidence not in evidence:
            evidence.append(f.evidence)

    unified = UnifiedFinding(
        fingerprint=fp,
        rule_id=winner.rule_id,
        type=winner.type,
        severity=winner.severity,
        confidence=winner.confidence if has_conflict else max(f.confidence for f in group),
        location=Location(file=winner.file, line=winner.line,
                          source_component=winner.source_component,
                          target_component=winner.target_component),
        evidence=evidence,
        conflict_resolved=all_resolved,
        alternatives=alternatives,
        provenance=sorted({f.source for f in group}),
    )
    return unified, records
