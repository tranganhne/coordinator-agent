# Coordinator Agent

Coordinator Agent nằm giữa **Consistency Checking Agent** và **Reporting Agent**. Agent này:

1. Tổng hợp findings thành bộ dữ liệu thống nhất (unified findings).
2. Hòa giải xung đột giữa các nguồn (`rule_engine`, `graph_matching`, `similarity`).
3. Chuẩn hóa schema đầu ra.
4. Chuẩn bị payload cho các agent khác.
5. Lưu kết quả trung gian.
6. Kiểm tra toàn vẹn dữ liệu trước khi ghi Kho tri thức (KB).
7. Đọc lịch sử lần quét trước.
8. Phân loại delta: **New / Persistent / Resolved**.
9. Ghi tầng unified của KB (agent duy nhất được ghi).
10. Gửi gói dữ liệu cho Reporting Agent (luồng tách riêng với luồng ghi KB).

Coordinator **không** quyết định thứ tự chạy agent, **không** retry, **không** sửa code. Những việc đó thuộc về LangGraph Orchestration.

## Cấu trúc thư mục

```
coordinator-agent/
├── main.py                     # Chạy từ dòng lệnh
├── config.yaml                 # Trọng số tin cậy, ngưỡng xung đột
├── requirements.txt
├── .env.example
├── samples/                    # 2 lần quét mẫu để thử
│   ├── scan_1.json
│   └── scan_2.json
├── coordinator_agent/
│   ├── schema.py               # Hợp đồng dữ liệu (Pydantic)
│   ├── config.py
│   ├── agent.py                # Subgraph LangGraph + CoordinatorAgent
│   ├── aggregation/            # (1) (2) (3)
│   ├── delta/                  # fingerprint + (8)
│   ├── knowledge/              # (6) (7) (9) - SQLite
│   ├── intermediate_store.py   # (5)
│   ├── payload_builder.py      # (4) (10)
│   └── strategy_planner.py     # Pha Plan: đề xuất chiến lược quét
└── tests/test_coordinator.py
```

## Cài đặt và chạy

Yêu cầu: Python 3.10 trở lên.

```bash
# 1. Tạo môi trường ảo
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS / Linux:
source .venv/bin/activate

# 2. Cài thư viện
pip install -r requirements.txt

# 3. (Tùy chọn) tạo file .env
cp .env.example .env        # Windows: copy .env.example .env

# 4. Chạy lần quét 1, rồi lần quét 2
python main.py --input samples/scan_1.json
python main.py --input samples/scan_2.json

# 5. Chạy test
python -m pytest -q
```

Kết quả được ghi vào thư mục `outputs/`:

- `<scan_id>_reporting_payload.json`: gói dữ liệu gửi Reporting Agent.
- `<scan_id>_downstream.json`: gợi ý đầu vào cho Code Analysis / Consistency Checking ở lần sau.

KB được lưu tại `data/kb.sqlite`. Muốn chạy lại từ đầu thì xóa thư mục `data/`.

### Kết quả mong đợi

Lần quét 1 có 4 finding mới. Trong đó có 1 xung đột đã tự hòa giải và 1 xung đột chưa hòa giải. Finding `f7-loi` sai schema nên bị loại và ghi vào cảnh báo.

Lần quét 2 là quét incremental, chỉ quét `controllers` và `services`. Kết quả:

| Loại | Số lượng | Giải thích |
| --- | --- | --- |
| New | 1 | `services -> external_api` |
| Persistent | 3 | Có 1 mục `ui -> database` gắn cờ *chưa quét lại* |
| Resolved | 1 | `order_controller.py` đã được sửa |

## Định dạng đầu vào

Xem `samples/scan_1.json`. Hai phần bắt buộc:

- `context`: gồm `project_id`, `scan_id`, `scan_scope` (`full` | `incremental`) và `scanned_modules`.
- `consistency_result.findings[]`: mỗi finding cần có `rule_id`, `type`, `severity`, `source_component`, `target_component`, `file`, `confidence` (0–1) và `source`.

## Dùng trong code (tích hợp với Orchestration)

```python
import asyncio
from coordinator_agent.agent import CoordinatorAgent

agent = CoordinatorAgent(kb_path="data/kb.sqlite")
result = asyncio.run(agent.run(input_dict))
payload = result.reporting_payload          # đưa cho Reporting Agent
print(payload.delta_summary, payload.kb_persisted)
```

Nếu máy chưa cài `langgraph`, agent tự chạy bằng bộ chạy tuần tự có cùng thứ tự node.
