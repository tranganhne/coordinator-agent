"""Kiểm thử Coordinator Agent. Chạy: python -m pytest -q"""
import asyncio
import json
from pathlib import Path

from coordinator_agent.agent import CoordinatorAgent
from coordinator_agent.aggregation.conflict_resolver import resolve
from coordinator_agent.config import Config
from coordinator_agent.delta.delta_analyzer import compare
from coordinator_agent.schema import (HistorySnapshot, Location, RawFinding, ScanContext,
                                      UnifiedFinding)

ROOT = Path(__file__).resolve().parent.parent
CFG = Config()


def raw(**kw):
    base = dict(id="x", rule_id="R1", type="forbidden_dependency", severity="high",
                source_component="a", target_component="b", file="a.py", confidence=0.9,
                source="rule_engine")
    base.update(kw)
    return RawFinding(**base)


def uf(fp, comp="a"):
    return UnifiedFinding(fingerprint=fp, rule_id="R1", type="forbidden_dependency", severity="high",
                          confidence=0.9, location=Location(file="a.py", source_component=comp,
                                                            target_component="b"))


# ---------------------------------------------------------- xung đột
def test_conflict_resolved_by_reliability():
    u, recs = resolve("fp", [raw(severity="high", confidence=0.95),
                             raw(severity="medium", confidence=0.8, source="graph_matching")], CFG)
    assert u.severity == "high" and u.conflict_resolved
    assert recs[0].resolution == "priority_by_reliability"


def test_conflict_unresolved_keeps_both():
    u, recs = resolve("fp", [raw(type="divergence", confidence=0.6, source="similarity"),
                             raw(type="absence", confidence=0.55, source="graph_matching")], CFG)
    assert not u.conflict_resolved
    assert len(u.alternatives) == 1
    assert recs[0].resolution == "unresolved"


def test_identical_sources_are_merged():
    u, recs = resolve("fp", [raw(confidence=0.7), raw(confidence=0.9, source="graph_matching")], CFG)
    assert u.conflict_resolved and u.confidence == 0.9
    assert recs[0].resolution == "merged"


# ---------------------------------------------------------- delta
def test_delta_three_categories():
    ctx = ScanContext(project_id="p", scan_id="s2")
    prev = HistorySnapshot(scan_id="s1", findings=[uf("A"), uf("B")])
    _, _, d = compare([uf("B"), uf("C")], prev, ctx)
    assert d.resolved == ["A"] and d.persistent == ["B"] and d.new == ["C"]


def test_incremental_out_of_scope_is_not_resolved():
    ctx = ScanContext(project_id="p", scan_id="s2", scan_scope="incremental", scanned_modules=["a"])
    prev = HistorySnapshot(scan_id="s1", findings=[uf("UI", comp="ui")])
    _, active, d = compare([], prev, ctx)
    assert d.resolved == [] and d.persistent == ["UI"]
    assert active[0].not_rescanned


# ---------------------------------------------------------- end-to-end
def test_end_to_end_two_scans(tmp_path):
    agent = CoordinatorAgent(kb_path=str(tmp_path / "kb.sqlite"), config=CFG)
    s1 = json.loads((ROOT / "samples/scan_1.json").read_text(encoding="utf-8"))
    s2 = json.loads((ROOT / "samples/scan_2.json").read_text(encoding="utf-8"))

    r1 = asyncio.run(agent.run(s1)).reporting_payload
    assert r1.kb_persisted
    assert r1.delta_summary.new == 4
    assert any("f7-loi" in w for w in r1.warnings)  # finding sai schema bị loại

    r2 = asyncio.run(agent.run(s2)).reporting_payload
    assert r2.kb_persisted and r2.baseline_scan_id == "scan-001"
    assert (r2.delta_summary.new, r2.delta_summary.persistent, r2.delta_summary.resolved) == (1, 3, 1)

    # Chạy lại cùng một lần quét: không sinh bản ghi trùng, kết quả giữ nguyên
    r2b = asyncio.run(agent.run(s2)).reporting_payload
    assert r2b.delta_summary == r2.delta_summary


def test_invalid_baseline_blocks_kb_write_but_still_reports(tmp_path):
    agent = CoordinatorAgent(kb_path=str(tmp_path / "kb.sqlite"), config=CFG)
    s1 = json.loads((ROOT / "samples/scan_1.json").read_text(encoding="utf-8"))
    s1["context"]["baseline_scan_id"] = "khong-ton-tai"
    r = asyncio.run(agent.run(s1)).reporting_payload
    assert not r.kb_persisted                 # nhánh ghi KB bị chặn
    assert r.findings                         # nhánh Reporting vẫn có dữ liệu
    assert any("không tồn tại" in e for e in r.errors)
