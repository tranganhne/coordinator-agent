# ADR-004: Quét incremental không được kết luận lỗi đã sửa

- **Trạng thái:** Đã chấp nhận
- **Bối cảnh:** Chiến lược thích ứng có thể chỉ quét một số module. Lỗi cũ ở module không được quét sẽ vắng mặt trong kết quả, nhưng vắng mặt không có nghĩa là đã sửa.
- **Quyết định:** Lỗi cũ thuộc module ngoài phạm vi quét được giữ ở **Persistent** kèm cờ `not_rescanned: true`. Chỉ khi module đó được quét lại mà lỗi không còn thì mới chuyển sang Resolved. Strategy Planner đề xuất quét lại các module này ở lần sau.
- **Hệ quả:**
  - (+) Không báo nhầm "đã sửa", tránh làm đẹp số liệu (benchmark S03, S08).
  - (−) Danh sách Persistent có thể chứa lỗi thực ra đã sửa, cho đến lần quét đầy đủ tiếp theo.
