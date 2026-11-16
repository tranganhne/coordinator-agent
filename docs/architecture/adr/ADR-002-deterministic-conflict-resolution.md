# ADR-002: Hòa giải xung đột bằng công thức tất định, không dùng LLM

- **Trạng thái:** Đã chấp nhận
- **Bối cảnh:** Rule Engine, Graph Matching và Similarity có thể báo khác nhau về cùng một lỗi (khác severity hoặc khác loại). Cần chọn kết quả cuối mà vẫn giải thích và lặp lại được khi làm thực nghiệm.
- **Quyết định:** Điểm = độ tin cậy của nguồn × confidence của finding. Trọng số mặc định: rule_engine 1.0, graph_matching 0.85, similarity 0.7. Nếu bên cao nhất hơn bên thứ hai ít nhất ε = 0.15 thì chọn bên cao nhất; nếu không thì giữ cả hai và đánh dấu `conflict_resolved: false`. Trọng số và ε nằm trong `config.yaml`.
- **Hệ quả:**
  - (+) Cùng đầu vào luôn cho cùng kết quả; chấm được bằng benchmark (S04, S08).
  - (+) Không tự ép kết luận khi bằng chứng ngang nhau, để dành cho người dùng xem lại.
  - (−) Trọng số là giả định ban đầu, cần hiệu chỉnh bằng thực nghiệm.
