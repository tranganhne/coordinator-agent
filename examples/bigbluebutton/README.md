# Ví dụ kiểm thử: BigBlueButton (benchmark ArDoCo)

Chạy Coordinator Agent trên dữ liệu thật thay vì dữ liệu mẫu tự bịa.

## Nguồn dữ liệu

| Dữ liệu | Lấy từ | Vai trò trong hệ thống |
| --- | --- | --- |
| `data/bbb.repository` | [ardoco/benchmark](https://github.com/ardoco/benchmark/tree/main/bigbluebutton/model_2021) – `model_2021/pcm` | **Mô hình kiến trúc** (12 thành phần): thứ Architecture Extraction cần tạo ra |
| `data/goldstandard_sam_2021-code_2023.csv` | benchmark – `goldstandards/` | Đáp án ánh xạ **thành phần kiến trúc → thư mục code** |
| `data/goldstandard_sad_2021-sam_2021_UME.csv` | benchmark – `goldstandards/` | Thành phần có trong mô hình nhưng tài liệu không nhắc tới (Recording Service) – dành cho phần Architecture Extraction |
| Mã nguồn | [ardoco/bigbluebutton](https://github.com/ardoco/bigbluebutton) | **Code thật** để quét (không chép vào repo này, tự tải về) |
| `data/mapping_extra.csv` | Nhóm tự bổ sung | Ánh xạ thêm thư mục Redis viết bằng Scala mà gold standard chưa có |
| `rules.yaml` | Nhóm tự đặt | 4 luật kiến trúc **ví dụ** để thử Rule Engine |
| `simulate_fix.yaml` | Nhóm tự đặt | Một commit sửa lỗi **giả lập** để thấy Resolved |

Mô hình và gold standard thuộc giấy phép MIT của benchmark ArDoCo (xem `data/LICENSE-ardoco-benchmark`).

## Luồng chạy

```
bbb.repository ──► design_graph()  ┐  (thay tạm cho Architecture Extraction)
                                   ├─► consistency() ──► CoordinatorAgent.run() ──► outputs/
mã nguồn BBB ────► code_graph()    ┘  (thay tạm cho      (code THẬT của Coordinator)
                   (thay tạm cho      Consistency Checking)
                    Code Analysis)
```

Ba hàm đầu trong `pipeline.py` chỉ là **bản thay thế tạm** để có đầu vào thật cho Coordinator. Khi agent của các bạn trong nhóm xong, thay từng hàm bằng agent thật.

## Cách chạy

```bash
# 1. Tải code BigBlueButton (bản mà benchmark dùng: commit 8fa2507, nhánh develop)
git clone --depth 1 --branch develop https://github.com/ardoco/bigbluebutton.git ../bbb-new

# 2. (Tùy chọn) Tải bản cũ v2.5 để so sánh 2 phiên bản thật
git clone --depth 1 --branch v2.5.x-release https://github.com/ardoco/bigbluebutton.git ../bbb-old

# 3. Chạy (từ thư mục gốc coordinator-agent, đã kích hoạt .venv)
python examples/bigbluebutton/run_demo.py --old ../bbb-old --new ../bbb-new
```

Repo BigBlueButton khá nặng (khoảng 350 MB). Bỏ `--old` nếu chỉ muốn tải một bản.

## Kết quả đã chạy thử

| Lần quét | Mô tả | New | Persistent | Resolved |
| --- | --- | --- | --- | --- |
| 1 | v2.5.x-release, quét toàn bộ | 10 | 0 | 0 |
| 2 | develop 8fa2507, quét toàn bộ | 0 | 10 | 0 |
| 3 | 8fa2507 + commit sửa giả lập, quét incremental (HTML5 Server, HTML5 Client) | 0 | 8 (7 chưa quét lại) | 2 |

Một vài phát hiện đáng chú ý trên code thật:

- **BBB web → Presentation Conversion** (divergence): mô hình vẽ chiều ngược lại (Presentation Conversion → BBB web), còn code `PresentationService.groovy` import `DocumentConversionService`.
- **HTML5 Server → HTML5 Client** (divergence + vi phạm luật R-BBB-04): `addMeeting.js` và `changeLayout.js` phía server import enum từ thư mục giao diện `imports/ui/`.
- Nhiều cạnh **absence** (ví dụ Apps → Redis DB): các thành phần giao tiếp qua kênh Redis/HTTP nên quét import không thấy. Đây là giới hạn của bộ quét tạm, không hẳn là lỗi kiến trúc.

Giữa v2.5 và 8fa2507 các phụ thuộc cấp thành phần không đổi, nên lần quét 2 toàn Persistent. Đó là kết quả thật. Lần quét 3 dùng commit sửa **giả lập** để minh họa Resolved và `not_rescanned`.

## Giới hạn của bộ quét tạm

- Chỉ phân giải import Java/Scala/Groovy và import tuyệt đối `/imports/...` của Meteor (JS), cộng dấu hiệu dùng thư viện Redis.
- HTML5 Client và HTML5 Server dùng chung thư mục trong gold standard. Bộ quét tách theo quy ước Meteor (`/server/` và `imports/ui/`), code dùng chung không gán cho bên nào.
- Chưa có bộ đáp án vi phạm cho BigBlueButton, nên ví dụ này kiểm tra **luồng chạy** của Coordinator, chưa đo Precision/Recall.
