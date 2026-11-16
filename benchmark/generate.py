"""Sinh bộ dữ liệu kiểm thử (benchmark) cho Coordinator Agent.

Mỗi kịch bản (scenario) gồm:
  scans/<scan_id>.json        : đầu vào cho Coordinator (giống kết quả Consistency Checking gửi sang)
  gold/delta.csv              : đáp án phân loại New / Persistent / Resolved cho từng lỗi ở từng lần quét
  gold/conflicts.csv          : đáp án hòa giải xung đột
  gold/summary.csv            : đáp án tổng hợp mỗi lần quét (số lượng, ghi KB, finding bị loại)
  scenario.json               : mô tả kịch bản và thứ tự các lần quét

Đáp án được VIẾT TỪ ĐẶC TẢ (S01-S07 viết tay, S08 suy ra từ "sự thật" mô phỏng),
KHÔNG lấy từ việc chạy Coordinator, nên có thể dùng để chấm Coordinator.

Chạy: python benchmark/generate.py
"""
from __future__ import annotations

import csv
import json
import random
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "scenarios"

RELIABILITY = {"rule_engine": 1.0, "graph_matching": 0.85, "similarity": 0.7}
EPS = 0.15


# ------------------------------------------------------------------ tiện ích
def f(fid, rule, src, dst, file, *, type="forbidden_dependency", sev="high", conf=0.9,
      source="rule_engine", line=1, evidence=""):
    return {"id": fid, "rule_id": rule, "type": type, "severity": sev, "source_component": src,
            "target_component": dst, "file": file, "line": line, "evidence": evidence or f"{src}->{dst}",
            "confidence": conf, "source": source}


def key(rule, src, dst, file):
    """Khóa dễ đọc của một lỗi; evaluate.py đổi khóa này thành fingerprint."""
    return f"{rule}|{src}|{dst}|{file}"


def scan(project, scan_id, findings, scope="full", modules=(), baseline=None):
    return {"context": {"project_id": project, "scan_id": scan_id, "commit_hash": f"c-{scan_id}",
                        "scan_scope": scope, "scanned_modules": list(modules),
                        "baseline_scan_id": baseline},
            "consistency_result": {"drift_score": 0.0, "findings": findings, "warnings": [], "errors": []}}


class Scenario:
    def __init__(self, sid, title, description):
        self.sid, self.title, self.description = sid, title, description
        self.runs, self.delta, self.conflicts, self.summary = [], [], [], []

    def add_scan(self, data, *, delta=None, conflicts=None, summary=None, run_label=None):
        sid = data["context"]["scan_id"]
        run = run_label or sid
        self.runs.append({"run": run, "file": f"scans/{run}.json", "scan_id": sid})
        for k, status, *rest in delta or []:
            self.delta.append({"run": run, "key": k, "expected_status": status,
                               "expected_not_rescanned": rest[0] if rest else False})
        for k, field, resolution, value, resolved in conflicts or []:
            self.conflicts.append({"run": run, "key": k, "field": field, "expected_resolution": resolution,
                                   "expected_value": value, "expected_conflict_resolved": resolved})
        if summary:
            self.summary.append({"run": run, **summary})
        self._data = getattr(self, "_data", {})
        self._data[run] = data

    def write(self):
        d = OUT / self.sid
        (d / "scans").mkdir(parents=True, exist_ok=True)
        (d / "gold").mkdir(exist_ok=True)
        for run, data in self._data.items():
            (d / "scans" / f"{run}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                                     encoding="utf-8")
        (d / "scenario.json").write_text(json.dumps(
            {"id": self.sid, "title": self.title, "description": self.description, "runs": self.runs},
            ensure_ascii=False, indent=2), encoding="utf-8")
        _csv(d / "gold" / "delta.csv", self.delta,
             ["run", "key", "expected_status", "expected_not_rescanned"])
        _csv(d / "gold" / "conflicts.csv", self.conflicts,
             ["run", "key", "field", "expected_resolution", "expected_value", "expected_conflict_resolved"])
        _csv(d / "gold" / "summary.csv", self.summary,
             ["run", "new", "persistent", "resolved", "kb_persisted", "dropped"])


def _csv(path, rows, cols):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def S(new, persistent, resolved, kb=True, dropped=0):
    return {"new": new, "persistent": persistent, "resolved": resolved, "kb_persisted": kb, "dropped": dropped}


# ------------------------------------------------------------------ S01..S07: viết tay
def s01():
    s = Scenario("S01_first_scan", "Lần quét đầu tiên",
                 "Không có lịch sử: mọi lỗi là New. Hai finding sai schema (confidence 1.2, severity lạ) bị loại.")
    A = f("a", "R1", "ui", "db", "src/ui/a.py")
    B = f("b", "R1", "ui", "db", "src/ui/b.py")
    C = f("c", "R2", "api", "ext", "src/api/c.py", sev="medium")
    bad1 = f("x1", "R1", "ui", "db", "src/ui/x.py", conf=1.2)
    bad2 = f("x2", "R1", "ui", "db", "src/ui/y.py", sev="urgent")
    s.add_scan(scan("p1", "s1", [A, B, C, bad1, bad2]),
               delta=[(key("R1", "ui", "db", "src/ui/a.py"), "new"), (key("R1", "ui", "db", "src/ui/b.py"), "new"),
                      (key("R2", "api", "ext", "src/api/c.py"), "new")],
               summary=S(3, 0, 0, dropped=2))
    return s


def s02():
    s = Scenario("S02_lifecycle", "Vòng đời lỗi qua 3 lần quét",
                 "A được sửa ở lần 2 rồi xuất hiện lại ở lần 3 (tính là New); B được sửa ở lần 3; D mới ở lần 2.")
    A, B = f("a", "R1", "ui", "db", "a.py"), f("b", "R1", "ui", "db", "b.py")
    C, D = f("c", "R2", "api", "ext", "c.py"), f("d", "R3", "svc", "ui", "d.py")
    kA, kB, kC, kD = (key("R1", "ui", "db", "a.py"), key("R1", "ui", "db", "b.py"),
                      key("R2", "api", "ext", "c.py"), key("R3", "svc", "ui", "d.py"))
    s.add_scan(scan("p2", "s1", [A, B, C]), delta=[(kA, "new"), (kB, "new"), (kC, "new")], summary=S(3, 0, 0))
    s.add_scan(scan("p2", "s2", [B, C, D]),
               delta=[(kA, "resolved"), (kB, "persistent"), (kC, "persistent"), (kD, "new")], summary=S(1, 2, 1))
    s.add_scan(scan("p2", "s3", [C, D, A]),
               delta=[(kA, "new"), (kB, "resolved"), (kC, "persistent"), (kD, "persistent")], summary=S(1, 2, 1))
    return s


def s03():
    s = Scenario("S03_incremental", "Quét incremental",
                 "Lần 2 chỉ quét module api: lỗi ở ui không được kết luận là đã sửa (not_rescanned). "
                 "Lần 3 quét toàn bộ mới xác nhận X đã sửa.")
    X, Y, Z = f("x", "R1", "ui", "db", "ui/x.py"), f("y", "R1", "api", "db", "api/y.py"), f("z", "R2", "api", "ext", "api/z.py")
    kX, kY, kZ = key("R1", "ui", "db", "ui/x.py"), key("R1", "api", "db", "api/y.py"), key("R2", "api", "ext", "api/z.py")
    s.add_scan(scan("p3", "s1", [X, Y, Z]), delta=[(kX, "new"), (kY, "new"), (kZ, "new")], summary=S(3, 0, 0))
    s.add_scan(scan("p3", "s2", [Y], scope="incremental", modules=["api"]),
               delta=[(kX, "persistent", True), (kY, "persistent"), (kZ, "resolved")], summary=S(0, 2, 1))
    s.add_scan(scan("p3", "s3", [Y]), delta=[(kX, "resolved"), (kY, "persistent")], summary=S(0, 1, 1))
    return s


def s04():
    s = Scenario("S04_conflicts", "Hòa giải xung đột",
                 "4 nhóm finding nhiều nguồn: ưu tiên theo độ tin cậy, không hòa giải được (2 nhóm), và gộp.")
    fs = [
        f("k1a", "R1", "ui", "db", "k1.py", sev="high", conf=0.95, source="rule_engine"),
        f("k1b", "R1", "ui", "db", "k1.py", sev="medium", conf=0.80, source="graph_matching"),
        f("k2a", "R9", "svc", "ui", "k2.py", type="divergence", sev="medium", conf=0.60, source="similarity"),
        f("k2b", "R9", "svc", "ui", "k2.py", type="absence", sev="medium", conf=0.55, source="graph_matching"),
        f("k3a", "R2", "api", "db", "k3.py", sev="high", conf=0.90, source="rule_engine"),
        f("k3b", "R2", "api", "db", "k3.py", sev="high", conf=0.70, source="graph_matching"),
        f("k4a", "R3", "api", "ext", "k4.py", sev="critical", conf=0.90, source="graph_matching"),
        f("k4b", "R3", "api", "ext", "k4.py", sev="low", conf=0.70, source="rule_engine"),
    ]
    k1, k2, k3, k4 = (key("R1", "ui", "db", "k1.py"), key("R9", "svc", "ui", "k2.py"),
                      key("R2", "api", "db", "k3.py"), key("R3", "api", "ext", "k4.py"))
    # điểm: k1 0.95 vs 0.68 (lệch 0.27) | k2 0.4675 vs 0.42 (0.0475) | k4 0.765 vs 0.70 (0.065)
    s.add_scan(scan("p4", "s1", fs),
               delta=[(k1, "new"), (k2, "new"), (k3, "new"), (k4, "new")],
               conflicts=[(k1, "severity", "priority_by_reliability", "high", True),
                          (k2, "type", "unresolved", "absence", False),
                          (k3, "severity", "merged", "high", True),
                          (k4, "severity", "unresolved", "critical", False)],
               summary=S(4, 0, 0))
    return s


def s05():
    s = Scenario("S05_normalization", "Chuẩn hóa dữ liệu",
                 "Severity viết hoa/bí danh (MAJOR, blocker) và đường dẫn kiểu Windows (./src\\ui\\a.py) "
                 "phải được chuẩn hóa để hai báo cáo của cùng một lỗi được gộp lại.")
    fs = [f("n1", "R1", "ui", "db", ".\\src\\ui\\a.py", sev="MAJOR", source="rule_engine"),
          f("n2", "R1", "ui", "db", "src/ui/a.py", sev="high", conf=0.8, source="graph_matching"),
          f("n3", "R2", "api", "db", "src/api/b.py", sev="blocker")]
    kn, kb = key("R1", "ui", "db", "src/ui/a.py"), key("R2", "api", "db", "src/api/b.py")
    s.add_scan(scan("p5", "s1", fs), delta=[(kn, "new"), (kb, "new")],
               conflicts=[(kn, "severity", "merged", "high", True)], summary=S(2, 0, 0))
    # kiểm tra severity cuối cùng của n3 bằng một dòng conflicts "none"
    s.conflicts.append({"run": "s1", "key": kb, "field": "severity", "expected_resolution": "none",
                        "expected_value": "critical", "expected_conflict_resolved": True})
    return s


def s06():
    s = Scenario("S06_integrity", "Toàn vẹn dữ liệu",
                 "Lần 1 chỉ định baseline không tồn tại: không được ghi KB nhưng vẫn phải gửi báo cáo. "
                 "Lần 2 vì thế vẫn là lần đầu tiên (mọi lỗi New).")
    A, B = f("a", "R1", "ui", "db", "a.py"), f("b", "R1", "ui", "db", "b.py")
    kA, kB = key("R1", "ui", "db", "a.py"), key("R1", "ui", "db", "b.py")
    s.add_scan(scan("p6", "s1", [A, B], baseline="khong-ton-tai"),
               delta=[(kA, "new"), (kB, "new")], summary=S(2, 0, 0, kb=False))
    s.add_scan(scan("p6", "s2", [A]), delta=[(kA, "new")], summary=S(1, 0, 0))
    return s


def s07():
    s = Scenario("S07_rerun", "Chạy lại cùng một lần quét",
                 "Orchestration retry lần quét s2: kết quả phải giống hệt, KB không sinh bản ghi trùng.")
    A, B = f("a", "R1", "ui", "db", "a.py"), f("b", "R1", "ui", "db", "b.py")
    kA, kB = key("R1", "ui", "db", "a.py"), key("R1", "ui", "db", "b.py")
    s.add_scan(scan("p7", "s1", [A, B]), delta=[(kA, "new"), (kB, "new")], summary=S(2, 0, 0))
    for run in ("s2", "s2_retry"):
        s.add_scan(scan("p7", "s2", [A]), run_label=run,
                   delta=[(kA, "persistent"), (kB, "resolved")], summary=S(0, 1, 1))
    return s


# ------------------------------------------------------------------ S08: tổng hợp quy mô lớn
def s08(seed=2026, n_scans=6):
    """Mô phỏng một dự án 8 module qua 6 lần quét. 'Sự thật' là tập vi phạm thật ở mỗi lần quét;
    mỗi vi phạm được 1-3 nguồn báo (có trùng lặp, có bất đồng severity). Đáp án suy ra từ sự thật."""
    rng = random.Random(seed)
    s = Scenario("S08_synthetic_large", "Dự án tổng hợp 8 module, 6 lần quét",
                 f"Sinh ngẫu nhiên có hạt giống {seed}: khoảng 60-90 vi phạm thật mỗi lần quét, "
                 "10% được sửa và 5-12 lỗi mới mỗi lần, lần quét 4 là incremental (3 module).")
    modules = ["ui", "api", "svc", "repo", "db", "auth", "cache", "ext"]
    sev_order = ["low", "medium", "high", "critical"]
    pool, counter = {}, 0

    def new_violation():
        nonlocal counter
        counter += 1
        a, b = rng.sample(modules, 2)
        k = (f"R{rng.randint(1, 6)}", a, b, f"{a}/file_{counter:03d}.py")
        pool[k] = rng.choice(sev_order)
        return k

    truth = {new_violation() for _ in range(70)}
    active: dict[tuple, bool] = {}  # lỗi đang mở sau lần quét trước -> not_rescanned?
    for t in range(1, n_scans + 1):
        if t > 1:
            fixed = set(rng.sample(sorted(truth), k=max(1, len(truth) // 10)))
            truth = (truth - fixed) | {new_violation() for _ in range(rng.randint(5, 12))}
        incremental = t == 4
        scanned = sorted(rng.sample(modules, 3)) if incremental else modules
        visible = {k for k in truth if k[1] in scanned}

        findings, conflicts, n = [], [], 0
        for k in sorted(visible):
            rule, a, b, file = k
            sources = rng.sample(list(RELIABILITY), k=rng.choice([1, 1, 2, 2, 3]))
            reports = []
            for src in sources:
                sev = pool[k] if rng.random() < 0.7 else rng.choice(sev_order)
                conf = round(rng.uniform(0.5, 0.99), 2)
                reports.append((src, sev, conf))
            for src, sev, conf in reports:
                n += 1
                findings.append(f(f"f{n}", rule, a, b, file, sev=sev, conf=conf, source=src))
            if len(reports) > 1:  # đáp án hòa giải theo công thức trong đặc tả
                scored = sorted(((RELIABILITY[s_] * c, sv) for s_, sv, c in reports), reverse=True)
                best = {}
                for sc, sv in scored:
                    best.setdefault(sv, sc)
                if len(best) == 1:
                    conflicts.append((key(*k), "severity", "merged", scored[0][1], True))
                else:
                    ranked = sorted(best.items(), key=lambda x: -x[1])
                    ok = ranked[0][1] - ranked[1][1] >= EPS
                    conflicts.append((key(*k), "severity", "priority_by_reliability" if ok else "unresolved",
                                      ranked[0][0], ok))
        # nhiễu: 2 finding sai schema mỗi lần quét
        findings.append(f("bad1", "R1", "ui", "db", "x.py", conf=1.7))
        findings.append(f("bad2", "R1", "ui", "db", "y.py", sev="???"))

        delta, new_active = [], {}
        for k in visible:
            status = "persistent" if k in active else "new"
            delta.append((key(*k), status))
            new_active[k] = False
        for k in active:
            if k in visible:
                continue
            if k[1] in scanned:
                delta.append((key(*k), "resolved"))
            else:
                delta.append((key(*k), "persistent", True))
                new_active[k] = True
        summ = S(sum(d[1] == "new" for d in delta), sum(d[1] == "persistent" for d in delta),
                 sum(d[1] == "resolved" for d in delta), dropped=2)
        s.add_scan(scan("p8", f"s{t}", findings, scope="incremental" if incremental else "full",
                        modules=scanned if incremental else ()),
                   delta=delta, conflicts=conflicts, summary=summ)
        active = new_active
    return s


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    for build in (s01, s02, s03, s04, s05, s06, s07, s08):
        sc = build()
        sc.write()
        print(f"{sc.sid:<22} {len(sc.runs)} lần quét, {len(sc.delta)} dòng đáp án delta, "
              f"{len(sc.conflicts)} dòng đáp án xung đột")


if __name__ == "__main__":
    main()
