# Bài 03 — Autonomy & Uncertainty

## Ý chính
- Câu hỏi cốt lõi: **phần nào được phép "không chắc chắn"** và **ai quyết định bước tiếp theo: code hay model?**
- Mỗi thí nghiệm trao thêm quyền cho model:

| File | Loại bất định | Ai chọn đường đi | Bản chất |
|---|---|---|---|
| `exp1_content.py` | Nội dung (câu chữ) | Code | Workflow |
| `exp2_outcome.py` | Kết quả (tool lỗi/thành công) | Code | Workflow + xử lý lỗi |
| `exp3_agent.py` | Đường đi (bước tiếp theo) | **Model** | Agent (bước đầu) |

## Exp1 — Bất định nội dung
- Luồng cố định: `lookup_order` → `get_policy` → `chat`.
- Cùng 1 đơn, 3 giọng khách khác nhau → **chỉ câu chữ thay đổi**, đường đi giữ nguyên.
- Prompt "chỉ dùng thông tin được cung cấp" → hạn chế model bịa.

## Exp2 — Bất định kết quả
- Tool có thể lỗi (`set_failures(n)` giả lập timeout).
- Retry: 1 lần gọi + 2 lần thử lại = tối đa 3 lần.
- Hết lượt thử → **fallback cố định, KHÔNG gọi LLM** → model không có cơ hội đoán bừa ETA.
- Mọi nhánh (thành công / retry / fallback) do người viết sẵn → vẫn là **workflow**.

## Exp3 — Bất định đường đi
- Model nhận danh sách action được phép và trả JSON `{"action", "args"}`.
- Model chỉ **PROPOSE** (đề xuất), còn code (harness) mới là bên **thực thi**.
- `observations` = trí nhớ của agent, mỗi bước được cập nhật thêm.
- Hiện mới làm 1 bước. Agent đầy đủ = vòng lặp: đề xuất → kiểm tra → thực thi → ghi nhận → lặp đến `finish`.
- Manh mối ẩn trong data: đơn trễ vì **khách đổi địa chỉ** (`ORDER_HISTORY`). Chỉ agent biết tự tra thêm `get_order_history` mới tìm ra nguyên nhân này.

## Đánh đổi
- Càng trao quyền: càng **linh hoạt** nhưng càng **khó dự đoán**.
- Rủi ro của agent: chọn sai bước, gọi action không tồn tại, JSON hỏng, lặp vô hạn.
- **Nguyên tắc:** chỉ dùng agent khi đường đi không thể viết trước. Viết trước được → dùng workflow.

## Việc cần làm khi dựng agent loop
- [ ] Bọc `json.loads` trong `try/except`.
- [ ] Kiểm tra `action` có nằm trong danh sách cho phép không, `args` có đúng không.
- [ ] Giới hạn số bước (`max_steps`).
- [ ] Lưu ý biến toàn cục `failures_left` giữ trạng thái giữa các lần gọi.
