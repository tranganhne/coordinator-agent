"""Chạy Coordinator Agent từ dòng lệnh.

Ví dụ:
    python main.py --input samples/scan_1.json
    python main.py --input samples/scan_2.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from coordinator_agent.agent import HAS_LANGGRAPH, CoordinatorAgent


def main() -> None:
    parser = argparse.ArgumentParser(description="Coordinator Agent")
    parser.add_argument("--input", required=True, help="File JSON đầu vào (context + consistency_result)")
    parser.add_argument("--db", default=None, help="Đường dẫn SQLite KB (mặc định: KB_PATH hoặc data/kb.sqlite)")
    parser.add_argument("--out", default="outputs", help="Thư mục ghi kết quả")
    args = parser.parse_args()

    data = json.loads(Path(args.input).read_text(encoding="utf-8"))
    agent = CoordinatorAgent(kb_path=args.db)
    result = asyncio.run(agent.run(data))

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = result.reporting_payload
    out_file = out_dir / f"{p.scan_id}_reporting_payload.json"
    out_file.write_text(json.dumps(p.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / f"{p.scan_id}_downstream.json").write_text(
        json.dumps(result.downstream_payloads, ensure_ascii=False, indent=2), encoding="utf-8")

    # ---- Tóm tắt ra màn hình
    print(f"Chế độ chạy     : {'LangGraph' if HAS_LANGGRAPH else 'tuần tự (chưa cài langgraph)'}")
    print(f"Project / Scan  : {p.project_id} / {p.scan_id} (baseline: {p.baseline_scan_id or 'không có'})")
    print(f"Delta           : New={p.delta_summary.new}  Persistent={p.delta_summary.persistent}  "
          f"Resolved={p.delta_summary.resolved}")
    unresolved = sum(1 for c in p.conflicts if c.resolution == "unresolved")
    print(f"Xung đột        : {len(p.conflicts)} (chưa hòa giải: {unresolved})")
    print(f"Ghi KB          : {'thành công' if p.kb_persisted else 'THẤT BẠI'}")
    for f in p.findings:
        flag = " [chưa quét lại]" if f.not_rescanned else ""
        flag += " [XUNG ĐỘT]" if not f.conflict_resolved else ""
        print(f"  - {f.delta_status:<10} {f.severity:<8} {f.location.source_component} -> "
              f"{f.location.target_component}  ({f.location.file}){flag}")
    for w in p.warnings:
        print(f"Cảnh báo: {w}")
    for e in p.errors:
        print(f"Lỗi: {e}")
    print("Đề xuất lần sau :", " | ".join(p.strategy_proposal.notes))
    print(f"Đã ghi: {out_file}")


if __name__ == "__main__":
    main()
