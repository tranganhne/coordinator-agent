"""Chấm điểm Coordinator Agent trên bộ benchmark.

Với mỗi kịch bản: tạo KB trống, chạy lần lượt các lần quét, so kết quả với đáp án (gold/).
Đo:
  - Phân loại delta: Precision / Recall / F1 cho từng lớp New, Persistent, Resolved
  - Cờ not_rescanned: độ chính xác
  - Hòa giải xung đột: độ chính xác của cách xử lý, giá trị cuối cùng, cờ conflict_resolved
  - Tổng hợp mỗi lần quét: số lượng New/Persistent/Resolved, ghi KB, số finding bị loại
  - Thời gian chạy trung bình mỗi lần quét

Chạy: python benchmark/evaluate.py      (kết quả ghi vào benchmark/results/)
"""
from __future__ import annotations

import asyncio
import csv
import json
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from coordinator_agent.agent import CoordinatorAgent  # noqa: E402
from coordinator_agent.config import Config  # noqa: E402
from coordinator_agent.delta.fingerprint import fingerprint  # noqa: E402
from coordinator_agent.schema import RawFinding  # noqa: E402

CLASSES = ("new", "persistent", "resolved")


def fp_of(k: str) -> str:
    rule, src, dst, file = k.split("|")
    return fingerprint(RawFinding(id="_", rule_id=rule, type="divergence", severity="low",
                                  source_component=src, target_component=dst, file=file,
                                  confidence=0.5, source="rule_engine"))


def read_csv(p: Path) -> list[dict]:
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def as_bool(v: str) -> bool:
    return str(v).strip().lower() == "true"


async def run_scenario(d: Path) -> dict:
    meta = json.loads((d / "scenario.json").read_text(encoding="utf-8"))
    gold_delta, gold_conf, gold_sum = (read_csv(d / "gold" / n) for n in ("delta.csv", "conflicts.csv", "summary.csv"))
    tmp = tempfile.mkdtemp()
    agent = CoordinatorAgent(kb_path=str(Path(tmp) / "kb.sqlite"), config=Config())

    pairs, nr_ok, nr_total = [], 0, 0
    conf_res = conf_val = conf_flag = conf_total = 0
    sum_ok, sum_total, times, errors = 0, 0, [], []
    for run in meta["runs"]:
        data = json.loads((d / run["file"]).read_text(encoding="utf-8"))
        t0 = time.perf_counter()
        p = (await agent.run(data)).reporting_payload
        times.append(time.perf_counter() - t0)
        by_fp = {f.fingerprint: f for f in p.findings}
        conf_by = {(c.fingerprint, c.field): c for c in p.conflicts}

        # delta
        gold_fps = set()
        for g in (r for r in gold_delta if r["run"] == run["run"]):
            fp = fp_of(g["key"])
            gold_fps.add(fp)
            pred = by_fp.get(fp)
            pairs.append((g["expected_status"], pred.delta_status if pred else "missing"))
            if pred is None:
                errors.append(f"{run['run']}: thiếu {g['key']}")
            elif pred.delta_status != g["expected_status"]:
                errors.append(f"{run['run']}: {g['key']} dự đoán {pred.delta_status}, đáp án {g['expected_status']}")
            nr_total += 1
            nr_ok += bool(pred) and pred.not_rescanned == as_bool(g["expected_not_rescanned"])
        for fp, pred in by_fp.items():  # dự đoán thừa (không có trong đáp án)
            if fp not in gold_fps:
                pairs.append(("extra", pred.delta_status))
                errors.append(f"{run['run']}: thừa {pred.rule_id}|{pred.location.source_component}|"
                              f"{pred.location.target_component}|{pred.location.file}")

        # xung đột
        for g in (r for r in gold_conf if r["run"] == run["run"]):
            fp = fp_of(g["key"])
            pred_f = by_fp.get(fp)
            rec = conf_by.get((fp, g["field"]))
            conf_total += 1
            pred_res = rec.resolution if rec else "none"
            conf_res += pred_res == g["expected_resolution"]
            conf_val += bool(pred_f) and getattr(pred_f, g["field"]) == g["expected_value"]
            conf_flag += bool(pred_f) and pred_f.conflict_resolved == as_bool(g["expected_conflict_resolved"])
            if pred_res != g["expected_resolution"]:
                errors.append(f"{run['run']}: xung đột {g['key']} dự đoán {pred_res}, đáp án {g['expected_resolution']}")

        # tổng hợp
        for g in (r for r in gold_sum if r["run"] == run["run"]):
            dropped = sum("Bỏ qua finding" in w for w in p.warnings)
            got = (p.delta_summary.new, p.delta_summary.persistent, p.delta_summary.resolved,
                   p.kb_persisted, dropped)
            exp = (int(g["new"]), int(g["persistent"]), int(g["resolved"]), as_bool(g["kb_persisted"]),
                   int(g["dropped"]))
            sum_total += 1
            sum_ok += got == exp
            if got != exp:
                errors.append(f"{run['run']}: tổng hợp {got} khác đáp án {exp}")

    return {"id": meta["id"], "title": meta["title"], "runs": len(meta["runs"]), "pairs": pairs,
            "nr": (nr_ok, nr_total), "conf": (conf_res, conf_val, conf_flag, conf_total),
            "sum": (sum_ok, sum_total), "time_ms": 1000 * sum(times) / max(len(times), 1), "errors": errors}


def prf(pairs: list[tuple[str, str]]) -> dict:
    out = {}
    for c in CLASSES:
        tp = sum(g == c and p == c for g, p in pairs)
        fp = sum(g != c and p == c for g, p in pairs)
        fn = sum(g == c and p != c for g, p in pairs)
        pr = tp / (tp + fp) if tp + fp else 1.0
        rc = tp / (tp + fn) if tp + fn else 1.0
        out[c] = {"precision": pr, "recall": rc, "f1": 2 * pr * rc / (pr + rc) if pr + rc else 0.0,
                  "support": tp + fn}
    return out


def pct(a, b):
    return f"{100 * a / b:.1f}% ({a}/{b})" if b else "–"


async def main() -> None:
    results = [await run_scenario(d) for d in sorted((HERE / "scenarios").iterdir()) if d.is_dir()]
    all_pairs = [p for r in results for p in r["pairs"]]
    overall = prf(all_pairs)

    lines = ["# Kết quả đánh giá Coordinator Agent trên benchmark", "",
             "## Theo kịch bản", "",
             "| Kịch bản | Số lần quét | Delta đúng | not_rescanned đúng | Xung đột đúng | Tổng hợp đúng | ms/lần quét |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        ok = sum(g == p for g, p in r["pairs"])
        c = r["conf"]
        lines.append(f"| {r['id']} – {r['title']} | {r['runs']} | {pct(ok, len(r['pairs']))} | "
                     f"{pct(*r['nr'])} | {pct(c[0], c[3])} | {pct(*r['sum'])} | {r['time_ms']:.1f} |")
    lines += ["", "## Phân loại delta (gộp mọi kịch bản)", "",
              "| Lớp | Precision | Recall | F1 | Số mẫu |", "| --- | --- | --- | --- | --- |"]
    for c, m in overall.items():
        lines.append(f"| {c} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']} |")
    tot = [sum(r["conf"][i] for r in results) for i in range(4)]
    lines += ["", "## Hòa giải xung đột (gộp)", "",
              f"- Cách xử lý đúng: {pct(tot[0], tot[3])}",
              f"- Giá trị cuối (severity/type) đúng: {pct(tot[1], tot[3])}",
              f"- Cờ conflict_resolved đúng: {pct(tot[2], tot[3])}", ""]
    errs = [e for r in results for e in r["errors"]]
    lines += ["## Sai khác so với đáp án", ""] + ([f"- {e}" for e in errs[:50]] or ["Không có."])
    report = "\n".join(lines) + "\n"

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    (out / "report.md").write_text(report, encoding="utf-8")
    (out / "metrics.json").write_text(json.dumps(
        {"delta": overall, "conflicts": dict(zip(("resolution", "value", "flag", "total"), tot)),
         "scenarios": [{k: v for k, v in r.items() if k != "pairs"} for r in results]},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
