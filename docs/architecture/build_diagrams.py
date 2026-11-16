"""Sinh sơ đồ từ mô hình kiến trúc coordinator_architecture.json.

- coordinator_component.puml : cú pháp C4-PlantUML (Container/Component/Rel), cùng kiểu
  mà Architecture Extraction Agent đọc được bằng parser PlantUML.
- coordinator_component.mmd  : Mermaid, để xem nhanh trên GitHub hoặc xuất PNG bằng mmdc.

Chạy: python docs/architecture/build_diagrams.py
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
g = json.loads((HERE / "coordinator_architecture.json").read_text(encoding="utf-8"))
nodes = {n["id"]: n for n in g["nodes"]}
inner = [n for n in g["nodes"] if n["properties"].get("parent") == "coordinator"]
outer = [n for n in g["nodes"] if n["properties"].get("parent") != "coordinator"]


def esc(s: str) -> str:
    return s.replace('"', "'")


# ---------------------------------------------------------------- PlantUML (C4)
lines = ["@startuml coordinator_component",
         "!include https://raw.githubusercontent.com/plantuml-stdlib/C4-PlantUML/master/C4_Component.puml",
         "LAYOUT_TOP_DOWN()", "title Coordinator Agent - mô hình thành phần (C4 Component)", ""]
for n in outer:
    kind = "ContainerDb" if n["type"] == "database" else "Container"
    tech = n["properties"].get("technology", "LangGraph" if n["id"] != "kb_raw" else "DB")
    lines.append(f'{kind}({n["id"]}, "{esc(n["name"])}", "{tech}", "{esc(n["properties"]["description"])}")')
lines += ["", 'Container_Boundary(coordinator, "Coordinator Agent") {']
for n in inner:
    p = n["properties"]
    task = f' [NV {p["task"]}]' if p.get("task", "-") != "-" else ""
    lines.append(f'  Component({n["id"]}, "{esc(n["name"])}", "{p["module"]}", "{esc(p["description"])}{task}")')
lines += ["}", ""]
for e in g["edges"]:
    lines.append(f'Rel({e["source_id"]}, {e["target_id"]}, "{esc(e["label"])}")')
lines += ["", "@enduml", ""]
(HERE / "coordinator_component.puml").write_text("\n".join(lines), encoding="utf-8")

# ---------------------------------------------------------------- Mermaid
m = ["flowchart TB"]
for n in outer:
    shape = ('[("', '")]') if n["type"] == "database" else ('["', '"]')
    m.append(f'  {n["id"]}{shape[0]}<b>{n["name"]}</b><br/><small>{esc(n["properties"]["description"])}</small>{shape[1]}')
m.append('  subgraph coordinator["Coordinator Agent"]')
m.append("    direction TB")
for n in inner:
    p = n["properties"]
    task = f' · NV {p["task"]}' if p.get("task", "-") != "-" else ""
    m.append(f'    {n["id"]}["<b>{n["name"]}</b><br/><small>{p["module"]}{task}</small>"]')
m.append("  end")
for e in g["edges"]:
    arrow = "-.->" if e["relationship_type"] == "dependency" else "-->"
    m.append(f'  {e["source_id"]} {arrow}|"{esc(e["label"])}"| {e["target_id"]}')
m += ["  classDef db fill:#eef3fb,stroke:#5b7db8;", "  classDef core fill:#e8f1fd,stroke:#2f6fd0,stroke-width:2px;",
      "  class kb_raw,kb_unified db;", "  class agent core;"]
(HERE / "coordinator_component.mmd").write_text("\n".join(m) + "\n", encoding="utf-8")
print("Đã sinh coordinator_component.puml và coordinator_component.mmd")
