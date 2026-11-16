"""Kiểm thử ví dụ BigBlueButton mà không cần tải mã nguồn BBB (dùng code giả lập rất nhỏ)."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "examples" / "bigbluebutton"))

from pipeline import build_input, component_paths, design_graph, owner  # noqa: E402

from coordinator_agent.agent import CoordinatorAgent  # noqa: E402
from coordinator_agent.config import Config  # noqa: E402


def test_design_graph_from_pcm():
    comps, edges = design_graph()
    assert len(comps) == 12
    assert ("FSESL", "FreeSWITCH") in edges
    assert ("HTML5 Client", "HTML5 Server") in edges


def test_owner_longest_prefix_and_html5_split():
    m = component_paths()
    assert owner("akka-bbb-fsesl/src/main/java/org/bigbluebutton/freeswitch/X.java", m) == "FreeSWITCH"
    assert owner("akka-bbb-fsesl/src/main/scala/org/bigbluebutton/Boot.scala", m) == "FSESL"
    assert owner("bigbluebutton-html5/imports/api/x/server/a.js", m) == "HTML5 Server"
    assert owner("bigbluebutton-html5/imports/ui/a.js", m) == "HTML5 Client"


def _fake_repo(root: Path, server_imports_ui: bool) -> None:
    ui = root / "bigbluebutton-html5/imports/ui/enums.js"
    srv = root / "bigbluebutton-html5/imports/api/m/server/add.js"
    ui.parent.mkdir(parents=True)
    srv.parent.mkdir(parents=True)
    ui.write_text("export const A = 1;\n")
    srv.write_text("import { A } from '/imports/ui/enums';\n" if server_imports_ui else "const A = 1;\n")


def test_pipeline_feeds_coordinator(tmp_path):
    old, new = tmp_path / "old", tmp_path / "new"
    _fake_repo(old, server_imports_ui=True)
    _fake_repo(new, server_imports_ui=False)
    agent = CoordinatorAgent(kb_path=str(tmp_path / "kb.sqlite"), config=Config())

    r1 = asyncio.run(agent.run(build_input(old, "bbb", "s1", "c1"))).reporting_payload
    assert any(f.rule_id == "R-BBB-04" for f in r1.findings)

    r2 = asyncio.run(agent.run(build_input(new, "bbb", "s2", "c2"))).reporting_payload
    resolved = [f for f in r2.findings if f.delta_status == "resolved"]
    assert {f.rule_id for f in resolved} == {"R-BBB-04", "REFLEXION"}
