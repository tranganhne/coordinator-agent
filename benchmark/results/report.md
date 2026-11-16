# Kết quả đánh giá Coordinator Agent trên benchmark

## Theo kịch bản

| Kịch bản | Số lần quét | Delta đúng | not_rescanned đúng | Xung đột đúng | Tổng hợp đúng | ms/lần quét |
| --- | --- | --- | --- | --- | --- | --- |
| S01_first_scan – Lần quét đầu tiên | 1 | 100.0% (3/3) | 100.0% (3/3) | – | 100.0% (1/1) | 25.5 |
| S02_lifecycle – Vòng đời lỗi qua 3 lần quét | 3 | 100.0% (11/11) | 100.0% (11/11) | – | 100.0% (3/3) | 13.2 |
| S03_incremental – Quét incremental | 3 | 100.0% (8/8) | 100.0% (8/8) | – | 100.0% (3/3) | 13.4 |
| S04_conflicts – Hòa giải xung đột | 1 | 100.0% (4/4) | 100.0% (4/4) | 100.0% (4/4) | 100.0% (1/1) | 19.9 |
| S05_normalization – Chuẩn hóa dữ liệu | 1 | 100.0% (2/2) | 100.0% (2/2) | 100.0% (2/2) | 100.0% (1/1) | 20.2 |
| S06_integrity – Toàn vẹn dữ liệu | 2 | 100.0% (3/3) | 100.0% (3/3) | – | 100.0% (2/2) | 12.1 |
| S07_rerun – Chạy lại cùng một lần quét | 3 | 100.0% (6/6) | 100.0% (6/6) | – | 100.0% (3/3) | 14.6 |
| S08_synthetic_large – Dự án tổng hợp 8 module, 6 lần quét | 6 | 100.0% (479/479) | 100.0% (479/479) | 100.0% (248/248) | 100.0% (6/6) | 17.1 |

## Phân loại delta (gộp mọi kịch bản)

| Lớp | Precision | Recall | F1 | Số mẫu |
| --- | --- | --- | --- | --- |
| new | 1.000 | 1.000 | 1.000 | 135 |
| persistent | 1.000 | 1.000 | 1.000 | 340 |
| resolved | 1.000 | 1.000 | 1.000 | 41 |

## Hòa giải xung đột (gộp)

- Cách xử lý đúng: 100.0% (254/254)
- Giá trị cuối (severity/type) đúng: 100.0% (254/254)
- Cờ conflict_resolved đúng: 100.0% (254/254)

## Sai khác so với đáp án

Không có.
