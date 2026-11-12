"""Đọc cấu hình từ config.yaml và biến môi trường (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:  # python-dotenv là tùy chọn
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass

DEFAULTS = {
    "source_reliability": {"rule_engine": 1.0, "graph_matching": 0.85, "similarity": 0.7},
    "conflict_epsilon": 0.15,
    "confidence_threshold": 0.7,
    "low_confidence_ratio_alert": 0.3,
    "severity_aliases": {"minor": "low", "info": "low", "moderate": "medium",
                         "major": "high", "blocker": "critical"},
}


@dataclass
class Config:
    source_reliability: dict = field(default_factory=lambda: dict(DEFAULTS["source_reliability"]))
    conflict_epsilon: float = DEFAULTS["conflict_epsilon"]
    confidence_threshold: float = DEFAULTS["confidence_threshold"]
    low_confidence_ratio_alert: float = DEFAULTS["low_confidence_ratio_alert"]
    severity_aliases: dict = field(default_factory=lambda: dict(DEFAULTS["severity_aliases"]))
    kb_path: str = "data/kb.sqlite"


def load_config(path: str | None = None) -> Config:
    path = path or os.getenv("CONFIG_PATH", "config.yaml")
    data: dict = {}
    if Path(path).exists():
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    merged = {**DEFAULTS, **data}
    return Config(
        source_reliability=merged["source_reliability"],
        conflict_epsilon=float(merged["conflict_epsilon"]),
        confidence_threshold=float(merged["confidence_threshold"]),
        low_confidence_ratio_alert=float(merged["low_confidence_ratio_alert"]),
        severity_aliases=merged["severity_aliases"],
        kb_path=os.getenv("KB_PATH", "data/kb.sqlite"),
    )
