"""Chạy Coordinator trên 2 phiên bản BigBlueButton để thấy New / Persistent / Resolved.

Cách dùng (xem README.md cùng thư mục để biết cách tải code BigBlueButton):
    python examples/bigbluebutton/run_demo.py --old <thư mục v2.5> --new <thư mục bản 8fa2507>
Chỉ có một phiên bản thì bỏ --old.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from coordinator_agent.agent import CoordinatorAgent  # noqa: E402
from pipeline import build_input, load_fix  # noqa: E402

OUT = Path(__file__).resolve().parent / "outputs"


def summarize(label: str, p) -> None:
    print(f"\n===== {label}: {p.scan_id} (baseline: {p.baseline_scan_id or 'không có'}) =====")
    print(f"Delta: New={p.delta_summary.new}  Persistent={p.delta_summary.persistent}  "
          f"Resolved={p.delta_summary.resolved}   | xung đột: {len(p.conflicts)} "
          f"(chưa hòa giải: {sum(c.resolution == 'unresolved' for c in p.conflicts)})   "
          f"| ghi KB: {'OK' if p.kb_persisted else 'THẤT BẠI'}")
    for f in p.findings:
        print(f"  {f.delta_status:<10} {f.severity:<8} {f.type:<20} "
              f"{f.location.source_component} -> {f.location.target_component}  [{f.rule_id}]"
              + ("  (chưa quét lại)" if f.not_rescanned else ""))
    for w in p.warnings:
        print("  Cảnh báo:", w)


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old", help="Thư mục code phiên bản cũ (vd. v2.5.x-release)")
    ap.add_argument("--new", required=True, help="Thư mục code phiên bản mới (vd. commit 8fa2507)")
    ap.add_argument("--db", default=str(OUT / "kb_bbb.sqlite"))
    ap.add_argument("--no-fix", action="store_true", help="Bỏ lần quét 3 (sửa lỗi giả lập)")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    Path(args.db).unlink(missing_ok=True)  # demo luôn chạy lại từ đầu
    agent = CoordinatorAgent(kb_path=args.db)

    scans = []
    if args.old:
        scans.append(("Lần quét 1 (bản cũ)", Path(args.old), "bbb-v2.5", "v2.5.x-release", None, None))
    scans.append((f"Lần quét {len(scans) + 1} (bản mới)", Path(args.new), "bbb-8fa2507", "8fa2507",
                  None, None))
    if not args.no_fix:
        scans.append((f"Lần quét {len(scans) + 1} (bản mới + commit sửa GIẢ LẬP, quét incremental)",
                      Path(args.new), "bbb-8fa2507-fix", "8fa2507+fix",
                      ["HTML5 Server", "HTML5 Client"], load_fix()))

    for label, path, scan_id, commit, modules, fix in scans:
        inp = build_input(path, "bigbluebutton", scan_id, commit, modules, fix)
        (OUT / f"{scan_id}_coordinator_input.json").write_text(
            json.dumps(inp, ensure_ascii=False, indent=2), encoding="utf-8")
        result = await agent.run(inp)
        payload = result.reporting_payload
        (OUT / f"{scan_id}_reporting_payload.json").write_text(
            json.dumps(payload.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        summarize(label, payload)
    print(f"\nĐã ghi kết quả vào: {OUT}")


if __name__ == "__main__":
    asyncio.run(main())
