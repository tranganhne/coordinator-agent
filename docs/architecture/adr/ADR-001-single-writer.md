# ADR-001: Coordinator là agent duy nhất ghi tầng unified của Kho tri thức

- **Trạng thái:** Đã chấp nhận
- **Bối cảnh:** Năm agent cùng đọc và ghi Kho tri thức. Nếu nhiều agent cùng ghi kết quả tổng hợp, dữ liệu dễ bị ghi đè hoặc mâu thuẫn, và khó biết bản nào là bản đúng.
- **Quyết định:** Chia KB thành hai tầng. Tầng **raw/audit**: mỗi agent ghi phần riêng của mình. Tầng **unified** (unified findings, delta, chiến lược quét): chỉ Coordinator được ghi. Mỗi lần ghi nằm trong một transaction và dùng upsert theo `(project_id, scan_id)`.
- **Hệ quả:**
  - (+) Không có xung đột ghi đồng thời; chạy lại một lần quét không sinh bản ghi trùng (benchmark S07).
  - (+) Có đúng một nơi chịu trách nhiệm kiểm tra toàn vẹn trước khi ghi.
  - (−) Coordinator thành điểm nghẽn ghi. Với quy mô đề tài (vài nghìn finding mỗi lần quét) chấp nhận được.
