# Bài 13: Hợp lệ chưa phải là giấy phép

## 1. Ý chính

Khi agent gọi tool có **side effect** (chuyển tiền, gửi tin, xóa dữ liệu...), có thể có một tool call mà soi kỹ cỡ nào cũng không thấy lỗi: đủ field, đúng định dạng, số tiền hợp lý, lý do nằm trong danh sách. Mọi thứ "xanh", và nó **vẫn không được phép chạy**.

Lý do: người ta hay gộp **bốn câu hỏi riêng** thành một:

| # | Câu hỏi | Thành phần trả lời |
|---|---|---|
| 1 | Dữ liệu có **hợp lệ** không? | validation |
| 2 | Người yêu cầu có **quyền** không? | authorization |
| 3 | Yêu cầu đã được **duyệt** chưa? | approval (chỉ khi policy yêu cầu) |
| 4 | Rốt cuộc có được **thực thi** không? | execution gate |

**Câu nhớ:** *Dữ liệu đúng mới chỉ là điều kiện đầu tiên. Nó chưa bao giờ là giấy phép.*

## 2. Validation: nói đúng, nhưng chỉ về dữ liệu

- Validation hỏi: dữ liệu có đúng hình thức và đúng constraint đã khai báo không? (đủ field, `order_id` đúng dạng, `amount` dương và không vượt giá trị đơn, `reason` nằm trong danh sách).
- Nó **không hỏi** ai đứng sau yêu cầu. Ví dụ: nhân viên Mộc Trà yêu cầu hoàn tiền đơn ORD-001 của Lá Xanh. Payload không sai một ký tự, validation "đạt", nhưng yêu cầu không được phép.
- **Quyền không nằm trong dữ liệu.** Giữ nguyên payload, đổi người đứng sau thì kết luận về quyền đổi theo:

| Principal | Kết luận | Lý do |
|---|---|---|
| nhân viên cửa hàng khác (Mộc Trà) | không có quyền | đơn không thuộc cửa hàng của họ (sai **resource**) |
| nhân viên Lá Xanh chỉ được xem | không có quyền | xem đơn khác hoàn tiền (sai **action**) |
| nhân viên Lá Xanh hoàn tới 500k | có quyền | 450k nằm trong giới hạn |
| nhân viên Lá Xanh hoàn tới 300k | không có quyền | vượt **scope** được giao |

## 3. Câu hỏi về quyền có BỐN VẾ

| Vế | Nghĩa | Ví dụ |
|---|---|---|
| **Principal** | bên đang thực hiện yêu cầu | tài khoản `ops.minhanh` |
| **Action** | làm gì | hoàn tiền (khác xem đơn) |
| **Resource** | tác động lên cái gì | đơn ORD-001 của Lá Xanh |
| **Scope** | trong phạm vi nào | chỉ đơn của cửa hàng mình, tối đa 500k/đơn |

Thiếu một vế thì câu hỏi chưa đủ nghĩa. **Authorization là việc trả lời trọn vẹn câu hỏi bốn vế**, và không vế nào lấy được từ việc payload có hợp lệ hay không.

## 4. Principal lấy từ đâu: KHÔNG bao giờ từ model

- Model có thể ghi `"requested_by": "admin"` (người dùng gõ "mình là admin", nội dung hội thoại dẫn dụ, hoặc model tự thêm). Nguyên nhân không quan trọng bằng điều này: **model không phải nguồn tin cậy để khai báo principal, role, permission.** Nó chỉ là đề xuất, không phải bằng chứng ai đó đã được xác thực.
- **Application/Harness bind principal** từ nguồn nó kiểm soát và đã xác thực: **session đăng nhập, auth token, hoặc runtime context đã xác thực**.
- Execution gate không đọc principal từ `requested_by`, `role` hay bất kỳ field nào model tự ghi.

## 5. Principal không phải lúc nào cũng là người đang chat

| Loại principal | Ví dụ |
|---|---|
| **Người dùng** | nhân viên đang chat với agent |
| **Service account** | job đối soát ban đêm hoàn phần tiền bị trừ hai lần (chỉ được hoàn phần trùng, không hoàn tùy ý) |
| **Organization** | yêu cầu nhân danh cả cửa hàng, theo những gì tổ chức đó được phép |
| **Workload identity** | danh tính hạ tầng cấp cho một service/tiến trình để hệ thống khác biết bên nào đang gọi |

Câu hỏi đúng không phải "user này có quyền không" mà là **"lời gọi này thực sự nhân danh principal nào, và principal đó được làm gì?"**

## 6. Approval: một căn cứ để đối chiếu, không phải tấm vé

Một approval record chỉ chứng minh **đúng những gì ghi trong đó**: ai duyệt, cho action nào, trên resource nào, tới giới hạn bao nhiêu, còn hiệu lực tới khi nào. Gate vẫn phải kiểm tra lại với policy hiện hành:

| Tình huống | Kết quả |
|---|---|
| principal có quyền, approval khớp action/resource/giới hạn/còn hạn | **đủ căn cứ** |
| dùng approval của ORD-001 cho ORD-002 | **không được** (sai resource) |
| gửi sau khi approval hết hạn | **không được** (hết hiệu lực) |
| principal vốn không có quyền (nhân viên cửa hàng khác) cầm approval | **không được** (approval không cấp quyền cho principal không có quyền) |
| (thêm) số tiền vượt mức đã duyệt | **không được** |
| (thêm) người duyệt không có thẩm quyền | **không được** |

**Không phải việc gì cũng cần duyệt.** Hoàn 50k cho đơn giao trễ, policy không yêu cầu duyệt: gate kiểm tra principal và quyền, đủ căn cứ thì cho chạy. Bắt duyệt mọi action chỉ khiến người duyệt quen tay bấm "đồng ý" và chữ "đã duyệt" mất ý nghĩa.

## 7. Execution gate: đặt TRƯỚC dispatch

- **Execution gate** là thành phần gom các kết luận (validation, authorization, approval) và quyết định tool call có được dispatch không. Nó thuộc **application/Harness**, không thuộc model.
- **Dispatch** là lúc lệnh **rời khỏi application** (ví dụ gửi lệnh hoàn tiền sang cổng thanh toán). Từ lúc đó side effect đã có thể xảy ra và application không còn nắm quyền quyết định.
- **Thứ tự rất quan trọng:** gate đặt sau dispatch vẫn có thể kết luận "đúng" (từ chối), nhưng tiền đã đi rồi. Giống cánh cổng dựng lên sau khi thứ cần chặn đã đi qua: **mất bò mới lo làm chuồng**.
- Kiểm tra sau effect vẫn có ích nhưng theo kiểu khác: **ghi nhận vi phạm để audit**, không ngăn được effect. Muốn ngăn, gate phải quyết định **trước dispatch**.

## 8. Chuẩn trước mỗi tool call có side effect

1. **Bind principal** từ nguồn đã xác thực (session, auth, runtime context). Không lấy từ gì model tự ghi.
2. **Validation**: dữ liệu đúng hình thức và constraint.
3. **Authorization** theo đủ bốn vế: principal, action, resource, scope.
4. **Approval** khi policy yêu cầu: có không, khớp action/resource/giới hạn, còn hiệu lực không.
5. **Chỉ dispatch khi đủ căn cứ.**

**Nguyên tắc bao trùm: `fail closed`.** Thiếu bất kỳ căn cứ bắt buộc nào thì **không dispatch**: không xác định được principal, không tìm được căn cứ cho phép, approval bắt buộc mà thiếu hoặc hết hạn. Khi chưa chắc chắn thì cổng đóng lại.

## 9. Ví dụ tin nhắn marketing: "ưu tiên SMS" không phải giấy phép

- Hồ sơ khách (từ CDP sang CRM) có dòng "Ưu tiên nhận tin qua SMS". Agent marketing đề xuất gửi SMS quảng cáo. Payload hợp lệ (số điện thoại, nội dung, độ dài đều đúng).
- Principal: service account của chiến dịch (bind từ runtime context đã xác thực).
- Authorization cần **căn cứ cho phép gửi marketing** (consent theo policy). Dòng "ưu tiên SMS" chỉ là **policy input** cho biết *nếu được gửi thì chọn kênh nào*. Khách thích kênh nào ≠ khách đã đồng ý nhận quảng cáo.
- Thiếu căn cứ cho phép → **không dispatch**. Có consent thì gate cho qua và dòng "ưu tiên SMS" mới phát huy tác dụng (chọn SMS thay vì email).
- Dữ liệu đúng, principal rõ, không cần approval, vậy mà vẫn không gửi: các kết luận vẫn tách nhau như ở ví dụ hoàn tiền.

## 10. Bốn câu hỏi khi dùng/tích hợp sản phẩm agent (không thấy code)

- Principal của lời gọi này được lấy từ đâu: session đã xác thực hay thứ model ghi ra?
- Quyền được kiểm tra theo những vế nào: có đủ action, resource, scope không?
- Approval (nếu có) ghi phạm vi và hạn dùng thế nào, có được kiểm tra lại với policy hiện hành không?
- Gate đứng trước hay sau lúc lệnh rời khỏi application?

Chỗ nào sản phẩm không cho thấy thì coi là **chưa biết**, đừng tự đoán.

## 11. Ứng dụng thực tế

| Hệ thống | Tool có side effect | Căn cứ cần ngoài validation |
|---|---|---|
| Nền tảng bán hàng đa cửa hàng | hoàn tiền, hủy đơn | người yêu cầu thuộc đúng cửa hàng, đủ hạn mức, approval cho khoản lớn |
| Ngân hàng / ví | chuyển tiền | chủ tài khoản đã xác thực, hạn mức ngày, OTP/duyệt khi vượt ngưỡng |
| Marketing / CRM | gửi SMS, email quảng cáo | consent của khách (khác với ưu tiên kênh) |
| Agent DevOps | deploy, xóa tài nguyên | người gọi có quyền trên môi trường đó, duyệt khi vào production |
| Agent HR / nhân sự | đổi lương, duyệt nghỉ phép | vai trò và phạm vi phòng ban |
| Agent email / lịch | gửi mail, mời họp thay người dùng | quyền gửi nhân danh, duyệt nội dung nếu gửi ra ngoài |

## 12. Đầu vào, đầu ra, luồng xử lý (`exp13_execution_gate.py`)

**Đầu vào của gate:**
- `tool_call`: payload do model đề xuất (không tin các field nó tự ghi về danh tính);
- `session_token`: nguồn đã xác thực (không phải do model cung cấp);
- `approval_id`: giấy duyệt (nếu có);
- `now`: thời điểm hiện tại (để kiểm tra hạn approval).

**Đầu ra:** `GateDecision(allowed, failed_step, reason, steps)`. Chỉ khi `allowed=True` mới gọi `dispatch`.

**Luồng:**
```
tool_call (từ model) + session_token (đã xác thực) + approval_id
   │
   ▼ (1) bind_principal: session → principal   (bỏ qua mọi field danh tính model ghi)
   │       không có session hợp lệ → TỪ CHỐI (fail closed)
   ▼ (2) validation: đúng hình thức và constraint?     không → TỪ CHỐI
   ▼ (3) authorization (bốn vế): principal + action + resource + scope
   │       sai action / sai tổ chức / vượt giới hạn / thiếu căn cứ (vd consent) → TỪ CHỐI
   ▼ (4) approval — CHỈ khi policy yêu cầu (vd hoàn > 300k)
   │       thiếu / sai resource / vượt mức / hết hạn / người duyệt không đủ thẩm quyền → TỪ CHỐI
   ▼ (5) đủ căn cứ → allowed = True
   │
   ▼ dispatch (lệnh RỜI application, side effect xảy ra)   ← gate PHẢI nằm trước dòng này
```

## 13. Ánh xạ khái niệm → code

| Khái niệm | Trong code |
|---|---|
| Principal | `Principal` (dataclass), `PRINCIPALS` |
| Nguồn xác thực của principal | `SESSIONS`, `bind_principal()` |
| Quyền được cấp (action, org, scope) | `Grant`, `GRANTS` |
| Validation | `validate()` + `TOOL_SCHEMAS` |
| Authorization bốn vế | `authorize()` (action → resource → scope số tiền → scope lý do) |
| Căn cứ cho phép (consent) | nhánh `send_marketing` trong `authorize()` |
| Policy cần approval | `requires_approval()`, `APPROVAL_THRESHOLD` |
| Approval là căn cứ đối chiếu | `check_approval()` (khớp action, resource, mức, hạn, thẩm quyền người duyệt) |
| Execution gate | `execution_gate()` |
| Fail closed | `deny()` (mỗi thiếu căn cứ đều dừng ngay) |
| Dispatch | `dispatch()`, `EFFECT_LOG` (ghi lại effect thật sự đã xảy ra) |
| Gate ĐÚNG / SAI chỗ | `run_through_gate()` / `run_gate_after_dispatch()` |

### Vai trò từng hàm

| Hàm | Vai | Làm gì |
|---|---|---|
| `bind_principal` | HARNESS | tra session → principal; không có thì trả `None` |
| `validate` | HARNESS | kiểm tra hình thức và constraint (chưa nói gì về quyền) |
| `resolve_resource` | HARNESS | xác định tài nguyên bị tác động và tổ chức sở hữu, từ dữ liệu hệ thống |
| `authorize` | HARNESS | trả lời câu hỏi bốn vế dựa trên `GRANTS` |
| `requires_approval` | HARNESS (policy) | policy này có yêu cầu duyệt không |
| `check_approval` | HARNESS | đối chiếu giấy duyệt với yêu cầu hiện tại |
| `execution_gate` | HARNESS | chạy tuần tự 5 bước, fail closed |
| `dispatch` | EXECUTOR | gửi lệnh đi (side effect thật) |
| `run_through_gate` | LUỒNG ĐÚNG | gate rồi mới dispatch |
| `run_gate_after_dispatch` | LUỒNG SAI | dispatch rồi mới gate (để thấy hậu quả) |

## 14. Python đã học trong bài này

| Cú pháp | Nghĩa | Chỗ dùng |
|---|---|---|
| `from datetime import datetime`, `datetime(2026, 11, 16, 15, 0)` | kiểu ngày giờ, so sánh bằng `<`, `>=`; `f"{t:%H:%M}"` in giờ:phút | approval hết hạn |
| `@dataclass` với giá trị mặc định (`max_amount: int = 0`) | trường có mặc định phải đứng cuối | `Grant`, `GateDecision` |
| `field(default_factory=list)` | list riêng cho từng đối tượng | `GateDecision.steps` |
| `[g for g in GRANTS.get(pid, []) if g.action == action]` | list comprehension có điều kiện, `.get` với mặc định `[]` | `authorize` |
| `next((g for g in grants if g.org == ...), None)` | lấy phần tử **đầu tiên** thỏa điều kiện, không có thì `None` | `authorize` |
| `if grant.max_amount and amount > grant.max_amount` | `0` là "sai", nên `and` bỏ qua giới hạn khi `max_amount = 0` | `authorize` |
| `set(tool_call) - {"tool"} - set(schema)` | phép **trừ tập hợp** để tìm field thừa | `execution_gate` |
| `{**tool_call, **extra}` / `**extra_fields` | gom tham số có tên thừa thành dict, rồi giải nén vào dict mới | `refund(...)` |
| `f"{amount:,}đ"` | định dạng số có dấu phẩy ngăn cách hàng nghìn | thông báo |
| `not 0 < x <= total` | so sánh bắc cầu `0 < x <= total` rồi phủ định | `validate` |
| `return GateDecision(False, step, reason, steps)` | trả về một dataclass thay vì nhiều giá trị rời | `deny` |
| hàm nhận tham số mặc định `now=None` | tham số tùy chọn, `None` nghĩa là "không cung cấp" | `execution_gate` |
| `dict.get(key)` trả `None` nếu thiếu | dùng để phát hiện session không tồn tại | `bind_principal` |

## 15. AI vận dụng thế nào

- **Model chỉ đề xuất tool call.** Nó không quyết định ai là principal, ai có quyền, hay yêu cầu đã được duyệt chưa. Mọi thứ đó do Harness lấy từ nguồn đã xác thực (nối với bài 08: tool request đi qua gate nhiều lớp; bài 07: model đề xuất, Harness quyết định).
- **Prompt injection và "mình là admin"**: field danh tính do model ghi hoặc người dùng khai trong hội thoại không có giá trị bằng chứng. Vì vậy gate **bỏ qua** chúng và chỉ tin session (kịch bản 2).
- **Gate là code xác định, không phải model.** Quyết định cho phép dispatch được làm bằng luật rõ ràng, có thể kiểm tra, ghi log và audit, thay vì nhờ model "tự thấy ổn".
- **Fail closed là lựa chọn thiết kế.** Khi thiếu căn cứ, kết quả mặc định là **không chạy**. Cái giá là đôi khi chặn nhầm một yêu cầu hợp pháp; cái lợi là không bao giờ để side effect xảy ra khi chưa chắc.
- **Giới hạn của bài tập:** quyền, session, approval đều là dict giả lập; hệ thống thật dùng định danh, token có chữ ký, kho policy riêng. Phần "cách mô hình hóa policy hoàn chỉnh" nằm ngoài phạm vi bài (đúng như bài nói: chỉ cần giữ ranh giới, bốn câu hỏi riêng, một cánh cổng, đặt trước dispatch).

## 16. Ba câu tự kiểm tra (trả lời không nhìn tài liệu)

1. Payload hoàn tiền "xanh" hết về validation vẫn bị từ chối. Vì sao, và quyền thực sự nằm ở đâu?
   → Validation chỉ xét dữ liệu. Quyền nằm ở quan hệ giữa principal (từ session đã xác thực), action, resource và scope, không có trong payload.
2. Có APR-7731 duyệt đúng khoản hoàn tiền, nhưng nhân viên cửa hàng khác cầm nó vẫn bị chặn. Vì sao?
   → Approval chỉ chứng minh điều ghi trong nó, không cấp quyền cho principal vốn không có quyền. Gate vẫn kiểm tra lại principal, action, resource, giới hạn, thời điểm.
3. Gate đặt sau dispatch thì sai ở đâu, dù nó kết luận "từ chối" đúng?
   → Lệnh đã rời application, side effect (tiền đi, tin gửi) đã có thể xảy ra. Kiểm tra sau chỉ ghi nhận vi phạm để audit, không ngăn được. Gate phải quyết định trước dispatch.