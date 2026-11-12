"""(1) Tổng hợp dữ liệu: gom các finding cùng fingerprint thành nhóm."""
from __future__ import annotations

from collections import OrderedDict

from ..delta.fingerprint import fingerprint
from ..schema import RawFinding


def aggregate(raw_findings: list[RawFinding]) -> "OrderedDict[str, list[RawFinding]]":
    """Trả về {fingerprint: [các RawFinding cùng chỉ một vấn đề]}.

    Nhóm 1 phần tử = không trùng; nhiều phần tử = nhiều nguồn cùng báo,
    sẽ được chuyển sang bước hòa giải xung đột.
    """
    groups: "OrderedDict[str, list[RawFinding]]" = OrderedDict()
    for f in raw_findings:
        groups.setdefault(fingerprint(f), []).append(f)
    return groups
