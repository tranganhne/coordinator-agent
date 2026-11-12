"""Coordinator Agent: subgraph LangGraph nội bộ + lớp vỏ bọc (Facade).

Thứ tự node:
  load_history -> aggregate -> resolve -> delta -> plan
      -> [write_kb  ||  build_report]   (hai nhánh tách biệt, chạy song song)
      -> finalize

Coordinator KHÔNG quyết định thứ tự chạy các agent khác và KHÔNG retry -
đó là việc của LangGraph Orchestration ở cấp hệ thống.
Nếu máy chưa cài langgraph, agent tự dùng bộ chạy tuần tự tương đương.
"""
from __future__ import annotations

import asyncio
from typing import Any, Optional, TypedDict

from pydantic import ValidationError

from .aggregation.aggregator import aggregate
from .aggregation.conflict_resolver import resolve
from .aggregation.normalizer import normalize_raw
from .config import Config, load_config
from .delta.delta_analyzer import compare
from .intermediate_store import IntermediateStore
from .knowledge.integrity import validate
from .knowledge.kb_reader import load_previous, load_strategy
from .knowledge.kb_writer import write_unified
from .payload_builder import build_for, build_reporting
from .schema import (CoordinatorInput, CoordinatorResult, RawFinding, UnifiedRecord,
                     ValidationReport)
from .strategy_planner import propose_strategy

try:
    from langgraph.graph import END, START, StateGraph
    HAS_LANGGRAPH = True
except ImportError:  # pragma: no cover
    HAS_LANGGRAPH = False


class CoordinatorState(TypedDict, total=False):
    inp: CoordinatorInput
    history: Any
    prev_strategy: Any
    raw_findings: list
    unified: list
    conflicts: list
    all_findings: list
    active: list
    delta: Any
    strategy: Any
    warnings: list
    errors: list
    validation: Any
    kb_persisted: bool
    reporting_payload: Any
    downstream: dict


class CoordinatorAgent:
    def __init__(self, kb_path: Optional[str] = None, config: Optional[Config] = None) -> None:
        self.cfg = config or load_config()
        self.kb_path = kb_path or self.cfg.kb_path
        self.store = IntermediateStore()
        self.graph = self._build_graph() if HAS_LANGGRAPH else None

    # ------------------------------------------------------------ các node
    async def node_load_history(self, s: CoordinatorState) -> dict:
        ctx = s["inp"].context
        history = await load_previous(self.kb_path, ctx.project_id, ctx.scan_id, ctx.baseline_scan_id)
        prev_strategy = await load_strategy(self.kb_path, ctx.project_id)
        return {"history": history, "prev_strategy": prev_strategy}

    async def node_aggregate(self, s: CoordinatorState) -> dict:
        inp = s["inp"]
        warnings = list(inp.consistency_result.warnings)
        errors = list(inp.consistency_result.errors)
        valid: list[RawFinding] = []
        for i, item in enumerate(inp.consistency_result.findings):
            fid = item.get("id", f"#{i}") if isinstance(item, dict) else f"#{i}"
            try:
                valid.append(normalize_raw(RawFinding.model_validate(item), self.cfg))
            except ValidationError as e:  # phải bắt trước ValueError (là lớp con)
                msg = "; ".join(f"{'.'.join(map(str, er['loc']))}: {er['msg']}" for er in e.errors())
                warnings.append(f"Bỏ qua finding {fid} (sai schema): {msg}")
            except ValueError as e:
                warnings.append(f"Bỏ qua finding {fid}: {e}")
        self.store.add(inp.context.scan_id, "raw_findings", valid)
        return {"raw_findings": self.store.all_batches(inp.context.scan_id),
                "warnings": warnings, "errors": errors}

    async def node_resolve(self, s: CoordinatorState) -> dict:
        unified, conflicts = [], []
        for fp, group in aggregate(s["raw_findings"]).items():
            u, recs = resolve(fp, group, self.cfg)
            unified.append(u)
            conflicts.extend(recs)
        return {"unified": unified, "conflicts": conflicts}

    async def node_delta(self, s: CoordinatorState) -> dict:
        ctx = s["inp"].context
        all_findings, active, delta = compare(s["unified"], s["history"], ctx)
        if ctx.baseline_scan_id and not s["history"].scan_id:
            # Baseline được chỉ định nhưng không tìm thấy -> để integrity chặn việc ghi KB
            delta.baseline_scan_id = ctx.baseline_scan_id
        return {"all_findings": all_findings, "active": active, "delta": delta}

    async def node_plan(self, s: CoordinatorState) -> dict:
        strategy = propose_strategy(s["inp"].context, s["active"], s["conflicts"],
                                    s.get("prev_strategy"), self.cfg)
        return {"strategy": strategy}

    async def node_write_kb(self, s: CoordinatorState) -> dict:
        ctx = s["inp"].context
        record = UnifiedRecord(
            project_id=ctx.project_id, scan_id=ctx.scan_id, commit_hash=ctx.commit_hash,
            active_findings=s["active"], delta=s["delta"], strategy=s["strategy"],
            current_count=len(s["unified"]), previous_count=len(s["history"].findings))
        report = validate(record, self.kb_path)
        if not report.ok:
            return {"validation": report, "kb_persisted": False}
        try:
            await write_unified(self.kb_path, record)
        except Exception as e:  # lỗi DB: không ném ra, trả về để Orchestration xử lý
            return {"validation": ValidationReport(ok=False, errors=[f"Lỗi ghi KB: {e}"]),
                    "kb_persisted": False}
        self.store.clear(ctx.scan_id)
        return {"validation": report, "kb_persisted": True}

    async def node_build_report(self, s: CoordinatorState) -> dict:
        inp = s["inp"]
        payload = build_reporting(inp.context, s["all_findings"], s["conflicts"], s["delta"],
                                  s["strategy"], inp.consistency_result.drift_score,
                                  s["warnings"], s["errors"])
        downstream = {name: build_for(name, s["strategy"])
                      for name in ("code_analysis", "consistency_checking")}
        return {"reporting_payload": payload, "downstream": downstream}

    async def node_finalize(self, s: CoordinatorState) -> dict:
        payload = s["reporting_payload"].model_copy(update={
            "kb_persisted": s["kb_persisted"],
            "errors": s["reporting_payload"].errors + s["validation"].errors,
        })
        return {"reporting_payload": payload}

    # ------------------------------------------------------------ đồ thị
    def _build_graph(self):
        g = StateGraph(CoordinatorState)
        for name in ("load_history", "aggregate", "resolve", "delta", "plan",
                     "write_kb", "build_report", "finalize"):
            g.add_node(name, getattr(self, f"node_{name}"))
        g.add_edge(START, "load_history")
        g.add_edge("load_history", "aggregate")
        g.add_edge("aggregate", "resolve")
        g.add_edge("resolve", "delta")
        g.add_edge("delta", "plan")
        g.add_edge("plan", "write_kb")        # nhánh 1: ghi KB
        g.add_edge("plan", "build_report")    # nhánh 2: gửi Reporting
        g.add_edge(["write_kb", "build_report"], "finalize")
        g.add_edge("finalize", END)
        return g.compile()

    async def _run_fallback(self, state: CoordinatorState) -> CoordinatorState:
        for node in (self.node_load_history, self.node_aggregate, self.node_resolve,
                     self.node_delta, self.node_plan):
            state.update(await node(state))
        a, b = await asyncio.gather(self.node_write_kb(state), self.node_build_report(state))
        state.update(a)
        state.update(b)
        state.update(await self.node_finalize(state))
        return state

    # ------------------------------------------------------------ API
    async def run(self, inp: CoordinatorInput | dict) -> CoordinatorResult:
        if isinstance(inp, dict):
            inp = CoordinatorInput.model_validate(inp)
        state: CoordinatorState = {"inp": inp}
        final = await self.graph.ainvoke(state) if self.graph else await self._run_fallback(state)
        return CoordinatorResult(reporting_payload=final["reporting_payload"],
                                 validation=final["validation"],
                                 downstream_payloads=final["downstream"])
