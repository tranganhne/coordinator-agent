"""Ví dụ kiểm thử Coordinator Agent trên dữ liệu thật: BigBlueButton (benchmark ArDoCo).

Ba bước đầu là BẢN THAY THẾ TẠM (stub) cho các agent của bạn trong nhóm,
chỉ để sinh dữ liệu đầu vào thật cho Coordinator:

  1. design_graph()  - thay cho Architecture Extraction: đọc mô hình PCM (bbb.repository)
  2. code_graph()    - thay cho Code Analysis: quét import Java/Scala/JS + dấu hiệu dùng Redis
  3. consistency()   - thay cho Consistency Checking: Reflexion Model + Rule Engine
  4. CoordinatorAgent.run() - phần THẬT của Coordinator

Ánh xạ thành phần kiến trúc -> thư mục code lấy từ gold standard
goldstandard_sam_2021-code_2023.csv của benchmark.
"""
from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
XSI = "{http://www.w3.org/2001/XMLSchema-instance}type"

# Các đường dẫn không phải code (gói cài đặt, file placeholder) -> bỏ qua khi quét
NON_CODE = ("build/packages-template/", ".placeholder.sh")
CODE_EXT = {".java", ".scala", ".groovy", ".js", ".jsx"}


# ============================================================ 1. ĐỒ THỊ THIẾT KẾ
def design_graph(repo_file: Path = DATA / "bbb.repository") -> tuple[dict, set]:
    """Đọc mô hình PCM: thành phần A 'required' interface do thành phần B 'provide' -> cạnh A->B."""
    root = ET.parse(repo_file).getroot()
    components, provides, requires = {}, {}, []
    for comp in root.findall("components__Repository"):
        name = comp.get("entityName")
        components[comp.get("id")] = name
        for role in comp.findall("providedRoles_InterfaceProvidingEntity"):
            provides[role.get("providedInterface__OperationProvidedRole")] = name
        for role in comp.findall("requiredRoles_InterfaceRequiringEntity"):
            requires.append((name, role.get("requiredInterface__OperationRequiredRole")))
    edges = {(a, provides[i]) for a, i in requires if i in provides and provides[i] != a}
    return components, edges


# ============================================================ ÁNH XẠ THÀNH PHẦN -> CODE
def component_paths(gold: Path = DATA / "goldstandard_sam_2021-code_2023.csv") -> list[tuple[str, str]]:
    """[(đường dẫn code, tên thành phần)] - chỉ lấy dòng 'Component:', bỏ đường dẫn không phải code."""
    out = []
    with gold.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            if not row["ae_name"].startswith("Component: "):
                continue
            path = row["ce_ids"]
            if any(t in path for t in NON_CODE):
                continue
            out.append((path, row["ae_name"].removeprefix("Component: ")))
    # Ánh xạ bổ sung do nhóm tự thêm (ghi rõ lý do trong file)
    extra = gold.parent / "mapping_extra.csv"
    if extra.exists():
        with extra.open(encoding="utf-8") as fh:
            out += [(r["path"], r["component"]) for r in csv.DictReader(fh)]
    # khớp tiền tố dài nhất trước (FreeSWITCH nằm bên trong thư mục FSESL)
    return sorted(out, key=lambda x: len(x[0]), reverse=True)


def owner(rel: str, mapping: list[tuple[str, str]]) -> str | None:
    """Thành phần sở hữu một file. HTML5 Client/Server dùng chung thư mục trong gold standard,
    nên tách thêm theo quy ước Meteor: '/server/' -> HTML5 Server, 'imports/ui/' hoặc '/client/'
    -> HTML5 Client, phần còn lại là code dùng chung và không gán cho bên nào."""
    for prefix, comp in mapping:
        if rel == prefix or rel.startswith(prefix):
            if comp in ("HTML5 Client", "HTML5 Server"):
                if "/server/" in rel:
                    return "HTML5 Server"
                if "/imports/ui/" in rel or "/client/" in rel:
                    return "HTML5 Client"
                return None  # code dùng chung (collection, utils): không gán cho bên nào
            return comp
    return None


# ============================================================ 2. ĐỒ THỊ THỰC TẾ TỪ CODE
RE_PKG = re.compile(r"^\s*package\s+([\w.]+)", re.M)
RE_JAVA_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)(\.\*)?\s*;?\s*$", re.M)
RE_SCALA_IMPORT = re.compile(r"^\s*import\s+([\w.]+)(?:\.(_|\{[^}]*\}))?", re.M)
RE_JS_IMPORT = re.compile(r"""(?:import\s[^'"]*?from\s*|import\s*\(?\s*|require\(\s*)['"](/imports/[^'"]+)['"]""")
RE_REDIS = re.compile(r"redis\.clients\.jedis|io\.lettuce|from\s+'redis'|require\('redis'\)|ioredis")


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def code_graph(code_root: Path, overrides: dict[str, list[tuple[str, str]]] | None = None
               ) -> dict[tuple[str, str], list[dict]]:
    """Trả về {(A, B): [bằng chứng]} với bằng chứng = {file, line, kind, text}.

    overrides = {đường dẫn file: [(chuỗi cũ, chuỗi mới)]} để giả lập một commit sửa code
    mà không phải chép lại cả repo.
    """
    overrides = overrides or {}
    mapping = component_paths()
    files: dict[str, tuple[Path, str | None]] = {}
    for p in code_root.rglob("*"):
        if p.suffix not in CODE_EXT or "node_modules" in p.parts or not p.is_file():
            continue
        rel = p.relative_to(code_root).as_posix()
        files[rel] = (p, owner(rel, mapping))

    # Chỉ mục FQN (Java/Scala) và đường dẫn module JS -> thành phần
    fqn, pkg = defaultdict(set), defaultdict(set)
    js_index = {}
    texts = {}
    for rel, (p, comp) in files.items():
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for old, new in overrides.get(rel, []):
            text = text.replace(old, new)
        texts[rel] = text
        if p.suffix in (".java", ".scala", ".groovy"):
            m = RE_PKG.search(text)
            if m:
                fqn[f"{m.group(1)}.{p.stem}"].add(comp)
                pkg[m.group(1)].add(comp)
        elif rel.startswith("bigbluebutton-html5/"):
            js_index[rel.removeprefix("bigbluebutton-html5").rsplit(".", 1)[0]] = comp

    def resolve_java(name: str, wildcard: bool) -> set:
        if wildcard:
            return set(pkg.get(name, ()))
        parts = name.split(".")
        while len(parts) > 1:  # bỏ dần tên thành viên / lớp lồng
            c = ".".join(parts)
            if c in fqn:
                return set(fqn[c])
            parts.pop()
        return set()

    def resolve_js(path: str) -> set:
        for cand in (path, path + "/index", path.rstrip("/") + "/index"):
            if cand in js_index:
                return {js_index[cand]}
        return set()

    edges: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for rel, text in texts.items():
        src = files[rel][1]
        if not src:
            continue
        ext = files[rel][0].suffix
        hits: list[tuple[set, int, str]] = []
        if ext in (".java", ".groovy"):
            for m in RE_JAVA_IMPORT.finditer(text):
                hits.append((resolve_java(m.group(1), bool(m.group(2))), m.start(), m.group(0).strip()))
        elif ext == ".scala":
            for m in RE_SCALA_IMPORT.finditer(text):
                hits.append((resolve_java(m.group(1), m.group(2) == "_") or resolve_java(m.group(1), True),
                             m.start(), m.group(0).strip()))
        else:
            for m in RE_JS_IMPORT.finditer(text):
                hits.append((resolve_js(m.group(1)), m.start(), m.group(0).strip()))
        for targets, pos, snippet in hits:
            if src in targets:
                continue  # trùng tên lớp: ưu tiên lớp cùng thành phần (vd. SystemConfiguration)
            for dst in targets:
                if dst and dst != src:
                    edges[(src, dst)].append({"file": rel, "line": _line_of(text, pos),
                                              "kind": "import", "text": snippet[:120]})
        # Dấu hiệu dùng thư viện Redis trực tiếp (thư viện ngoài, không có trong repo)
        m = RE_REDIS.search(text)
        if m and src not in ("Redis PubSub", "Redis DB"):
            dst = "Redis PubSub" if re.search(r"subscribe|publish", text, re.I) else "Redis DB"
            edges[(src, dst)].append({"file": rel, "line": _line_of(text, m.start()),
                                      "kind": "library", "text": m.group(0)})
    return dict(edges)


# ============================================================ 3. CONSISTENCY (STUB)
INFRA = {"Redis PubSub", "Redis DB", "FreeSWITCH", "kurento", "WebRTC-SFU"}


def consistency(design: set, actual: dict, rules_file: Path = HERE / "rules.yaml",
                code_present: set | None = None) -> list[dict]:
    """Sinh danh sách finding theo đúng định dạng đầu vào của Coordinator.

    - graph_matching: cạnh có trong code nhưng không có trong thiết kế (divergence),
      dựa trên import đã phân giải được (độ tin cậy cao).
    - similarity: cùng loại cạnh nhưng chỉ dựa trên dấu hiệu dùng thư viện (độ tin cậy thấp).
    - graph_matching: cạnh có trong thiết kế nhưng không thấy trong code (absence).
    - rule_engine: cạnh trong code vi phạm luật trong rules.yaml.
    Mỗi cạnh dùng 'file' = tên thành phần nguồn để mọi nguồn cùng báo về một cạnh có chung fingerprint.
    """
    rules = yaml.safe_load(rules_file.read_text(encoding="utf-8"))["rules"]
    findings: list[dict] = []
    n = 0

    def add(**kw):
        nonlocal n
        n += 1
        findings.append({"id": f"f{n}", **kw})

    for (a, b), ev in sorted(actual.items()):
        imports = [e for e in ev if e["kind"] == "import"]
        libs = [e for e in ev if e["kind"] == "library"]
        base = dict(source_component=a, target_component=b, file=f"component/{a}")
        if (a, b) not in design:
            sev = "medium" if b in INFRA else "high"
            if imports:
                e = imports[0]
                add(rule_id="REFLEXION", type="divergence", severity=sev, line=e["line"],
                    evidence=f"{e['file']}:{e['line']} {e['text']} (+{len(imports) - 1} import khác)",
                    confidence=0.9, source="graph_matching", **base)
            if libs:
                e = libs[0]
                add(rule_id="REFLEXION", type="divergence", severity="low", line=e["line"],
                    evidence=f"{e['file']}:{e['line']} dùng thư viện '{e['text']}'",
                    confidence=0.6, source="similarity", **base)
        for r in rules:
            f = r["forbid"]
            src_ok = f["from"] in ("*", a) and a not in f.get("except", [])
            if src_ok and b in f["to"]:
                e = (imports or libs)[0]
                add(rule_id=r["id"], type="forbidden_dependency", severity=r["severity"], line=e["line"],
                    evidence=f"{r['description']} | {e['file']}:{e['line']} {e['text']}",
                    confidence=0.95, source="rule_engine", **base)

    for a, b in sorted(design):
        if (a, b) in actual:
            continue
        if code_present is not None and a not in code_present:
            continue  # thành phần không có code trong repo (vd. kurento) -> không kết luận được
        add(rule_id="REFLEXION", type="absence", severity="low", source_component=a, target_component=b,
            file=f"component/{a}", line=0, confidence=0.5, source="graph_matching",
            evidence="Thiết kế có phụ thuộc nhưng không tìm thấy trong code "
                     "(có thể giao tiếp qua kênh Redis/HTTP mà quét import không thấy)")
    return findings


def load_fix(path: Path = HERE / "simulate_fix.yaml") -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in yaml.safe_load(path.read_text(encoding="utf-8"))["edits"]:
        out[e["file"]].append((e["old"], e["new"]))
    return dict(out)


def build_input(code_root: Path, project_id: str, scan_id: str, commit: str,
                modules: list[str] | None = None, overrides: dict | None = None) -> dict:
    """modules = None -> quét toàn bộ; có danh sách -> quét incremental chỉ các thành phần đó."""
    _, design = design_graph()
    actual = code_graph(code_root, overrides)
    present = {owner(r, component_paths()) for r in
               (p.relative_to(code_root).as_posix() for p in code_root.rglob("*")
                if p.suffix in CODE_EXT and "node_modules" not in p.parts)} - {None}
    findings = consistency(design, actual, code_present=present)
    if modules:
        findings = [f for f in findings if f["source_component"] in modules]
    return {
        "context": {"project_id": project_id, "scan_id": scan_id, "commit_hash": commit,
                    "scan_scope": "incremental" if modules else "full",
                    "scanned_modules": modules or [], "baseline_scan_id": None},
        "consistency_result": {"drift_score": round(len([k for k in actual if k not in design])
                                                    / max(len(actual), 1), 2),
                               "findings": findings, "warnings": [], "errors": []},
    }
