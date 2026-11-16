"""Chạy benchmark của Coordinator như một bài test: mọi kịch bản phải khớp đáp án."""
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmark"))

import evaluate  # noqa: E402


def test_benchmark_matches_gold():
    scen = sorted(d for d in (ROOT / "benchmark" / "scenarios").iterdir() if d.is_dir())
    assert len(scen) == 8
    for d in scen:
        r = asyncio.run(evaluate.run_scenario(d))
        assert r["errors"] == [], f"{r['id']}: {r['errors'][:5]}"
