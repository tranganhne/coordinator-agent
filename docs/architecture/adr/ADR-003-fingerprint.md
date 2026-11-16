# ADR-003: Định danh lỗi bằng fingerprint không chứa số dòng

- **Trạng thái:** Đã chấp nhận
- **Bối cảnh:** Để biết một lỗi là mới, còn tồn tại hay đã sửa, cần nhận ra "cùng một lỗi" qua các lần quét, trong khi code giữa hai lần quét luôn thay đổi.
- **Quyết định:** `fingerprint = SHA-256(rule_id + thành phần nguồn + thành phần đích + đường dẫn file đã chuẩn hóa)`, cắt 16 ký tự. Không dùng số dòng.
- **Hệ quả:**
  - (+) Sửa code ở chỗ khác trong file không làm lỗi cũ bị coi là lỗi mới.
  - (−) Hai lỗi cùng luật, cùng cặp thành phần, trong cùng một file sẽ bị gộp làm một. Ở cấp kiến trúc điều này chấp nhận được.
  - (−) Đổi tên hoặc chuyển file thì lỗi cũ thành Resolved và lỗi mới thành New.
