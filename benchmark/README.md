# Benchmark cho Coordinator Agent

Bộ dữ liệu kiểm thử **riêng cho Coordinator**: đầu vào là kết quả mà Consistency Checking gửi sang, kèm **đáp án (gold standard)** cho những gì Coordinator phải làm: phân loại delta, hòa giải xung đột, ghi Kho tri thức. Dùng để chấm điểm Coordinator bằng số liệu (Precision / Recall / F1), không phụ thuộc vào dữ liệu của agent khác.

## Cấu trúc

```
benchmark/
├── generate.py              # Sinh toàn bộ kịch bản + đáp án
├── evaluate.py              # Chạy Coordinator trên từng kịch bản và chấm điểm
├── scenarios/
│   └── S0x_<tên>/
│       ├── scenario.json    # Mô tả + thứ tự các lần quét
│       ├── scans/*.json     # Đầu vào Coordinator cho từng lần quét
│       └── gold/
│           ├── delta.csv     # run, key, expected_status, expected_not_rescanned
│           ├── conflicts.csv # run, key, field, expected_resolution, expected_value, expected_conflict_resolved
│           └── summary.csv   # run, new, persistent, resolved, kb_persisted, dropped
└── results/
    ├── report.md            # Bảng kết quả
    └── metrics.json
```

`key` có dạng `rule_id|nguồn|đích|file`. Bộ chấm điểm tự đổi khóa này thành fingerprint.

## Các kịch bản

| Mã | Kiểm tra điều gì | Nhiệm vụ liên quan |
| --- | --- | --- |
| S01 | Lần quét đầu: mọi lỗi là New; loại finding sai schema (confidence 1.2, severity lạ) | 1, 3, 8 |
| S02 | Vòng đời 3 lần quét: sửa → Resolved; lỗi đã sửa xuất hiện lại → New | 7, 8 |
| S03 | Quét incremental: lỗi ngoài phạm vi không được coi là đã sửa (`not_rescanned`) | 8 |
| S04 | Hòa giải xung đột: ưu tiên theo độ tin cậy, không hòa giải được, gộp | 2 |
| S05 | Chuẩn hóa: `MAJOR`, `blocker`, đường dẫn kiểu Windows `.\src\ui\a.py` | 3 |
| S06 | Toàn vẹn: baseline không tồn tại thì không ghi KB nhưng vẫn gửi báo cáo | 6, 9, 10 |
| S07 | Chạy lại cùng một lần quét (retry): kết quả giống hệt, KB không trùng | 9 |
| S08 | Dự án tổng hợp 8 module, 6 lần quét, khoảng 480 dòng đáp án, có nhiễu và bất đồng giữa các nguồn | tất cả |

Đáp án được viết **từ đặc tả**, không lấy từ kết quả chạy Coordinator:

- S01–S07 viết tay, mỗi kịch bản có giải thích trong `scenario.json`.
- S08 sinh từ một "sự thật" mô phỏng: tập vi phạm thật ở mỗi lần quét, có hạt giống ngẫu nhiên cố định nên chạy lại vẫn ra đúng dữ liệu cũ.

## Chạy

```bash
python benchmark/generate.py     # chỉ cần khi sửa kịch bản
python benchmark/evaluate.py     # chấm điểm, ghi benchmark/results/report.md
```

## Kết quả hiện tại

Coordinator đạt **100%** trên cả 8 kịch bản: F1 = 1.000 cho New, Persistent và Resolved; 254/254 xung đột xử lý đúng.

Để chắc bộ chấm điểm thật sự bắt được lỗi, nhóm đã thử **cố tình làm hỏng** Coordinator:

| Lỗi cố tình | Kết quả chấm |
| --- | --- |
| Đặt ngưỡng xung đột 0.05 thay vì 0.15 | Xung đột xử lý đúng giảm còn 86,6% |
| Bỏ qua quét incremental | F1 lớp Resolved giảm còn 0,48 |

## Giới hạn

- Benchmark chấm **logic của Coordinator so với đặc tả**, không chấm chất lượng phát hiện vi phạm (đó là việc của Consistency Checking).
- Dữ liệu là mô phỏng. Khi có kết quả thật từ Consistency Checking, thêm kịch bản mới vào `generate.py` theo cùng định dạng.
