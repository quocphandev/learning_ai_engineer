# Bài 14: Có guardrails rồi, action đã thật sự bị chặn chưa?

## 1. Ý chính
**Verdict đúng ≠ action bị chặn.** "Guardrails" là một chữ gộp 3 việc khác nhau:

| Việc | Vai | Làm gì | KHÔNG làm gì |
|---|---|---|---|
| **Check** | tạo tín hiệu | xem action/output, trả `pass / fail / review / điểm số` | không giữ action lại |
| **Gate** | enforce quyết định | nằm TRÊN đường tới action, đọc tín hiệu, ra `allow / deny / escalate` | không tự nghĩ ra tín hiệu |
| **HITL** | con người phán đoán | giữ action, chuyển cho người có thẩm quyền, quyết định QUAY VỀ GATE | không đi vòng qua gate |

Ẩn dụ: verdict = tấm biển "cần kiểm tra" bên lề đường. Gate = thanh chắn nằm ngang đường, có quyền không mở.

## 2. Sự cố mẫu
Email bồi thường được check gắn `REVIEW`, log ghi đúng, nhưng giữa agent và bước gửi không có gate → email vẫn tới khách.
Check không hỏng. Cái thiếu là thứ đứng chắn.

## 3. Luồng đúng
```
agent soạn email (proposal, chưa là action)
   → CHECK  → verdict (pass/fail/review)
   → GATE   đọc verdict (+ authorization, approval nếu có)
        ├─ allow    → executor gửi
        ├─ deny     → dừng
        └─ escalate → HITL giữ lại → người duyệt: đồng ý / từ chối / sửa
                                       └→ quyết định QUAY VỀ GATE → executor
```

## 4. Người duyệt sửa nội dung: đừng mở cửa sau
- Bản sửa KHÔNG phải "bản đã duyệt". Nó là **đề xuất mới**: verdict cũ không còn nói gì về nó.
- Bản sửa phải **check lại + authorize lại + qua gate lại**, rồi mới tới executor.
- Người duyệt cũng gõ nhầm được (thêm một số 0). Nếu bản sửa đi thẳng executor, đó là cửa sau.
- Giấy duyệt gắn với **nội dung** (fingerprint), không chỉ với id: đổi nội dung thì giấy duyệt cũ hết giá trị.

## 5. Cái giá của HITL
Bắt mọi email chờ người: latency tăng → hàng đợi phình → **approval fatigue** (bấm đồng ý theo quán tính) → phán đoán con người bị bào mòn đúng lúc cần nhất.
HITL là nguồn lực đắt và có hạn: chỉ dùng cho action mà phán đoán của người tạo khác biệt. Biết lúc nào KHÔNG cần hỏi người cũng là một phần của HITL đúng.

## 6. Đánh giá sản phẩm tự nhận "có guardrails"
- Guardrails chỉ bảo vệ những gì chúng **thật sự kiểm tra** và **thật sự enforce**.
- Badge "safe" = có bước đánh giá đã chạy. Chưa nói gì về việc có gate dùng điểm đó để chặn.
- Log `REVIEW` = check đã nhận ra vấn đề. Chưa nói action đã bị chặn.
- Không thấy bằng chứng gate → **chưa biết** (không có nghĩa là không an toàn, cũng không có nghĩa là đã được bảo vệ).
- Hai câu hỏi hỏi nhà cung cấp:
  1. Check nằm ở đâu, verdict chỉ được ghi log hay có gate đọc nó?
  2. Người duyệt sửa nội dung thì bản sửa có quay về gate không?

## 7. Ánh xạ khái niệm → code (`exp14_check_gate_hitl.py`)
| Khái niệm | Trong code |
|---|---|
| Đề xuất của agent (chưa là action) | `Proposal` (có `fingerprint()` cho nội dung) |
| Verdict | `Verdict(level, reasons)` |
| Check | `check_email()` (chỉ trả verdict) |
| Executor (chặng có effect thật) | `send_email()` ghi vào `SENT_LOG` |
| Gate | `gate()` trả `GateDecision(allow/deny/escalate)` |
| Pipeline đúng: check → gate → executor | `run_through_gate()` |
| HITL + quyết định quay về gate | `handle_review()` (approve / reject / edit) |
| Giấy duyệt gắn nội dung | `approvals: {proposal_id: fingerprint}` |
| Đọc bằng chứng | `conclude()` |

### Vai trò từng hàm
| Hàm | Vai | Làm gì |
|---|---|---|
| `check_email` | CHECK | nhận xét theo luật, trả verdict, không chặn |
| `gate` | GATE | đọc verdict + giấy duyệt, ra allow/deny/escalate; thiếu verdict → deny |
| `run_through_gate` | HARNESS | chỉ gọi `send_email` khi gate nói `allow` |
| `handle_review` | HITL | nhận quyết định người; `edit` tạo `Proposal` mới và chạy lại cả pipeline |
| `send_email` | EXECUTOR | gửi thật (ở đây ghi `SENT_LOG`) |
| `conclude` | NGƯỜI ĐỌC | kết luận chỉ từ bằng chứng có |

### Năm kịch bản (`python exp14_check_gate_hitl.py`)
| # | Kịch bản | Kết quả |
|---|---|---|
| 1 | Có check, không gate | log REVIEW, email vẫn gửi |
| 2 | Có gate | lần 1 `escalate` (không gửi), sau duyệt `allow`; cụm cấm → `deny` |
| 3 | Người duyệt sửa | gửi thẳng bản sửa: lọt 2,500,000đ; qua gate: `deny`; sửa hợp lý: `allow`; đổi nội dung giữ id: `escalate` |
| 4 | Chi phí HITL | mọi email qua người: 100 trong hàng đợi, 2 email xấu lọt; chỉ email rủi ro: 9 trong hàng đợi, 0 lọt |
| 5 | Đọc bằng chứng | badge/log REVIEW → "chưa biết"; cần gate deny + xác nhận executor không chạy |

## 8. Python trong bài
| Cú pháp | Nghĩa | Chỗ dùng |
|---|---|---|
| `@dataclass` + `field(default_factory=list)` | class chứa dữ liệu; list mặc định phải qua `default_factory` | `Verdict`, `Proposal` |
| `hashlib.sha256(raw.encode()).hexdigest()[:10]` | băm chuỗi thành dấu vân tay, lấy 10 ký tự đầu | `fingerprint` |
| `return Verdict("fail", [...])` sớm | gặp luật nặng nhất thì trả ngay | `check_email` |
| `dict.get(key)` trả `None` nếu không có | "chưa ai duyệt" | `gate` |
| `kind, *rest` / `_, a, b = tuple` | bung tuple quyết định | `handle_review` |
| `Proposal(proposal_id + "-v2", ...)` | tạo đối tượng mới thay vì sửa đối tượng cũ | bản sửa |
| hàm lồng hàm (`simulate`, `tired_reviewer`) | hàm phụ chỉ dùng trong một kịch bản | kịch bản 4 |
| `sys.argv`, `if __name__ == "__main__"` | tham số dòng lệnh, điểm vào | `main` |

## 9. AI nằm ở đâu
- **Agent** soạn email = proposal.
- **Check** có thể là luật cứng (như trong code) hoặc LLM-as-judge (chấm giọng điệu, rủi ro pháp lý). LLM-judge chỉ là một nguồn tín hiệu, có thể sai, nên KHÔNG tự nó là gate.
- **Gate** nên là logic xác định trong Harness, không để model tự quyết "mình có được gửi không".
- **HITL**: AI có thể tóm tắt vì sao email bị REVIEW giúp người duyệt, nhưng quyết định vẫn quay về gate.

## 10. Ba câu tự kiểm tra
1. Check trả `REVIEW` đúng mà email vẫn gửi đi. Cái gì thiếu?
   → Gate nằm trên đường tới executor. Verdict chỉ có tác dụng chặn khi có thứ đọc nó và có quyền không cho đi tiếp.
2. Người duyệt sửa nội dung email, có cho gửi luôn bản sửa không? Vì sao?
   → Không. Bản sửa là đề xuất mới, verdict cũ không áp dụng; phải check + authorize lại rồi quay về gate. Người duyệt cũng có thể nhầm.
3. Sản phẩm hiện badge "safe" và có log REVIEW. Kết luận được gì về việc action đã bị chặn?
   → Chưa kết luận được. Mới có bằng chứng check đã chạy. Cần bằng chứng gate đã đọc verdict và executor không chạy.