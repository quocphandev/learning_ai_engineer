# Result correlation: kết quả đúng nhưng gán nhầm chỗ vẫn thành sai

## 1. Ý chính

Chữ "đúng" mang **hai nghĩa khác nhau**:

| Câu hỏi | Ai chịu trách nhiệm |
|---|---|
| Result này có đúng **NỘI DUNG** không? | **Tool** (trả đúng dữ liệu cho yêu cầu đó) |
| Result này có về đúng **NƠI NHẬN** không? | **Harness** (result correlation: ghép result với đúng call sinh ra nó) |

- "Tool trả về đúng rồi" chỉ trả lời được **một nửa**. Nửa còn lại là ghép đúng chỗ.
- Ví dụ: hai lượt tra ORD-001 và ORD-002 chạy cùng lúc, mỗi lượt đều đúng. Nhưng result của ORD-002 về trước. Harness ghép theo vị trí ("result đầu thuộc call đầu") nên RunState bị **điền chéo**. Agent báo ORD-001 đã hủy, ORD-002 mai tới. Không mảnh nào hỏng, câu trả lời vẫn sai hoàn toàn.

## 2. Vì sao ghép theo vị trí/thứ tự về là sai

- Thứ tự result về là chuyện **xảy ra lúc chạy**, không ai định trước: hôm nay ORD-002 xong trước, mai ORD-001 xong trước.
- Một quy tắc dựa vào thứ không kiểm soát được thì chỉ đúng khi may mắn.
- **Hậu quả không dừng ở một câu trả lời sai**: lỗi đã nằm trong RunState, mọi bước sau đọc hai ô điền chéo đều mang lỗi theo (đặt lại nhầm đơn, ghi chú nhầm mã đơn...). Mỗi quyết định trông hợp lệ vì dữ liệu nó dựa vào là dữ liệu thật.
- **Lỗi lọt qua mọi lần thử đơn giản**: khi mỗi lượt chỉ có 1 call thì ghép theo vị trí luôn đúng, vì không còn cách nào để sai. Lỗi chỉ lộ khi có **từ 2 call trở lên** và result về lệch thứ tự. "Đã chạy ổn nhiều lần" chưa phải bằng chứng ghép đúng.

## 3. Giải pháp: identity ổn định của call (call_id)

Ẩn dụ quầy gửi đồ: thẻ số 17 được phát **ngay lúc gửi**, và lúc trả thì tìm theo **số trên thẻ**, không theo thứ tự khách quay lại.

Bốn tính chất của identity:
1. **Có trước khi call rời đi.** Xác lập trước dispatch, không suy ra sau khi result đã về (lúc đó lại phải đoán).
2. **Đi suốt hành trình.** request → lúc thực thi → result trả về → bước cập nhật state. Rơi ở bất kỳ chặng nào thì việc ghép quay về chuyện đoán.
3. **Nguồn không cố định.** Provider/protocol cấp sẵn, hoặc Harness tự tạo, hoặc nhận từ provider rồi chuẩn hóa. Tên hay gặp là `call_id`, nhưng không có field chung ở mọi hệ thống. Điều cần giữ là **tính chất**, không phải cái tên.
4. **Ai dùng thế nào:**
   - **Executor**: trả result kèm identity của đúng call vừa chạy. Không cần biết result ghi vào đâu.
   - **Harness**: dùng identity tìm đúng call gốc, ghép result, cập nhật đúng phần RunState.
   - **Model**: không phải đoán result nào thuộc call nào. Việc ghép là việc cơ học có căn cứ, do Harness làm.

## 4. Identity đúng ≠ result đúng

Identity khớp chỉ chứng minh result **về đúng nơi nhận**. Nó KHÔNG chứng minh:
- result lấy từ đúng nguồn,
- nội dung đúng (có thể là dữ liệu cũ/sai),
- call có đủ quyền để chạy,
- công việc đã thực sự hoàn tất.

Hai phép kiểm tra **độc lập theo cả hai chiều**: nội dung đúng không cứu được result gán nhầm chỗ; gán đúng chỗ cũng không biến nội dung sai thành đúng.
Call **không bao giờ trả result** thì không có gì để ghép: nằm ngoài phạm vi result correlation.

## 5. Lối tắt "nhìn nội dung" cũng không đứng vững

- Result chứa mã đơn → "nhìn mã đơn là biết ô nào" chỉ tình cờ chạy được vì hai mã đơn khác nhau và result ghi đúng mã.
- Ví dụ hai lượt tra cùng chặng Hà Nội: Đà Nẵng: tuyến, giờ bay, giá có thể **trùng hệt**. Dùng nội dung để đoán nơi nhận là trộn lẫn hai câu hỏi ở mục 1. Nội dung không phân biệt được thì bó tay; nội dung sai thì còn tự tin đặt sai chỗ.
- Cách đứng vững ở cả hai tình huống: **call identity** có trước khi call rời đi, không phụ thuộc result nói gì.

## 6. Khi agent trả lời nhầm đối tượng: đừng vội kết luận "lỗi correlation"

Output nhắm sai đối tượng chỉ là **triệu chứng**. Ít nhất có 3 nguyên nhân:

| Nguyên nhân | Dấu hiệu trong dấu vết |
|---|---|
| **WRONG_REQUEST**: call gửi đi với mã sai ngay từ đầu | request đã mang sai tham số |
| **CONTENT_ERROR**: nguồn/executor trả nhầm dữ liệu | result mang identity A (call tra ORD-001) nhưng chứa dữ liệu ORD-002, và được ghi **đúng ô của A** |
| **CORRELATION_ERROR**: Harness ghi nhầm ô | result mang A chứa đúng dữ liệu ORD-001 nhưng bị ghi vào ô **của B** |

Để khẳng định correlation là root cause, cần thấy:
- identity của từng request và từng result;
- result nào đã được ghi vào phần nào của state.

Nếu không có dấu vết (không có debug view/log): ghép sai result **chỉ là giả thuyết**. Nói: "Có thể do ghép sai result, nhưng mình chưa kiểm chứng được." Đừng nói "chắc chắn do ghép sai". Nội dung sai và ghi sai chỗ có thể xảy ra cùng lúc, nên thấy nội dung sai chưa đủ để nói bước ghép đã đúng.

## 7. Ứng dụng thực tế

| Hệ thống | Tình huống nhiều call song song | Rủi ro nếu ghép theo thứ tự |
|---|---|---|
| Bot CSKH | tra nhiều đơn, nhiều khách trong một lượt | báo nhầm trạng thái đơn |
| Agent đặt vé / du lịch | tra nhiều chặng, nhiều hãng, nhiều ngày | gán nhầm giá/giờ bay cho chặng |
| Agent tài chính / kế toán | tra số dư nhiều tài khoản | chuyển/báo nhầm tài khoản |
| Agent lập trình | đọc nhiều file, chạy nhiều test song song | gán lỗi test cho nhầm file |
| Agent tổng hợp nghiên cứu | gọi nhiều nguồn cùng lúc | trích nhầm nguồn cho claim (nối với bài hallucination) |
| Hệ thống đa agent | nhiều agent trả kết quả về một điều phối viên | điền nhầm phần việc của agent khác |

Quy tắc chung: **có từ 2 call song song trở lên thì phải ghép theo identity.**

## 8. Đầu vào, đầu ra, luồng xử lý (`exp_result_correlation.py`)

**Đầu vào:**
- danh sách call (mỗi call có `call_id`, tool, arguments, ô đích `slot`);
- các result trả về (mang `call_id`), theo thứ tự về (do độ trễ quyết định);
- danh sách đơn khách hỏi (cho phần chẩn đoán).

**Đầu ra:** RunState (các ô đã ghi) + câu trả lời gửi khách + `Trace` (dấu vết) + nhãn chẩn đoán nguyên nhân.

**Luồng:**
```
Harness tạo call ──► cấp identity (call_001, call_002)   ← TRƯỚC khi gửi
      │
      ▼ dispatch cùng lúc (từ chối nếu call chưa có identity)
 Executor chạy (mỗi call xong ở thời điểm riêng)
      │ trả ToolResult(call_id, content)
      ▼ result về THEO THỨ TỰ XONG (call_002 trước, call_001 sau)
 Harness: sổ "đang chờ" {call_id: call}
      │ result.call_id → pop khỏi sổ → biết call gốc → biết ô đích
      │   (không có identity khớp → KHÔNG ghi, không đoán)
      ▼
 write_slot(slot, content) → cập nhật RunState + ghi Trace
      ▼
 Model/agent đọc RunState → trả lời khách
```

## 9. Ánh xạ khái niệm → code

| Khái niệm | Trong code |
|---|---|
| Call có identity | `ToolCall.call_id`, `CallFactory.make_call()` |
| Identity có TRƯỚC dispatch | `make_call` cấp ngay khi tạo; `dispatch_and_collect` ném `ValueError` nếu `call_id` rỗng |
| Identity đi suốt hành trình | executor trả `ToolResult(call.call_id, ...)` |
| Result về theo thứ tự xong | `asyncio.as_completed(tasks)` |
| Ghép sai (theo thứ tự) | `correlate_by_position()` (dùng `zip`) |
| Ghép đúng (theo identity) | `correlate_by_identity()` (sổ `pending` + `pop`) |
| Lối tắt nhìn nội dung | `correlate_by_content()` (kết quả mơ hồ) |
| Cập nhật RunState | `write_slot()` |
| Dấu vết để chẩn đoán | `Trace.requests`, `Trace.results`, `Trace.writes` |
| Phân biệt nguyên nhân | `diagnose()` → `WRONG_REQUEST` / `CONTENT_ERROR` / `CORRELATION_ERROR` / `UNKNOWN` |

### Vai trò từng hàm

| Hàm / class | Vai | Làm gì |
|---|---|---|
| `CallFactory.make_call` | HARNESS | tạo call và cấp identity ngay lúc tạo |
| `dispatch_and_collect` | HARNESS | kiểm tra identity, ghi request vào Trace, gửi mọi call cùng lúc, thu result theo thứ tự về |
| `execute_call` | EXECUTOR | chạy call (có độ trễ riêng), trả result kèm đúng `call_id` |
| `correlate_by_position` | HARNESS (sai) | ghép result thứ n với call thứ n |
| `correlate_by_identity` | HARNESS (đúng) | ghép theo `call_id`; không khớp thì từ chối ghi |
| `write_slot` | HARNESS | ghi vào RunState và ghi dấu vết |
| `diagnose` | NGƯỜI ĐỌC | nhìn Trace, phân loại nguyên nhân hoặc nói "chưa đủ bằng chứng" |

## 10. Python đã học trong bài này

| Cú pháp | Nghĩa | Chỗ dùng |
|---|---|---|
| `async def` / `await` | hàm bất đồng bộ; `await` chờ một việc xong mà không chặn các việc khác | `execute_call` |
| `asyncio.sleep(0.2)` | chờ 0.2 giây (kiểu bất đồng bộ) để giả lập độ trễ | executor |
| `asyncio.create_task(coro)` | cho một hàm async bắt đầu chạy nền ngay | `dispatch_and_collect` |
| `asyncio.as_completed(tasks)` | duyệt các task theo thứ tự **xong trước ra trước** | thu result |
| `asyncio.run(coro)` | chạy một hàm async từ code thường (đồng bộ) | các kịch bản |
| `class X:` + `def __init__(self)` | class có hàm khởi tạo; `self._counter` là dữ liệu riêng của từng đối tượng | `CallFactory` |
| `itertools.count(1)` + `next(c)` | bộ đếm vô hạn 1, 2, 3...; `next` lấy số kế tiếp | cấp identity |
| `f"call_{n:03d}"` | định dạng số thành 3 chữ số, thêm số 0 đầu (`1` → `001`) | `make_call` |
| `zip(a, b)` | ghép từng cặp phần tử theo **vị trí** (chính là cách ghép sai) | `correlate_by_position` |
| `{c.call_id: c for c in calls}` | dict comprehension: tạo dict từ list | `pending` |
| `d.pop(key, None)` | lấy phần tử ra khỏi dict (thiếu khóa thì trả `None`, không lỗi) | `correlate_by_identity` |
| `[c for c in calls if ...]` | list comprehension có điều kiện | `correlate_by_content` |
| `raise ValueError("...")` + `except ValueError as error` | chủ động ném lỗi và bắt lại | chặn dispatch thiếu identity |
| `**executor_options` | gom mọi tham số có tên thừa thành dict rồi chuyển tiếp xuống hàm khác | `dispatch_and_collect` |
| `(d or {}).get(k, default)` | an toàn khi `d` là `None` | `execute_call` |
| `{x!r}` | hiển thị kèm dấu nháy (thấy được chuỗi rỗng `''`) | log |
| `f"{text:<34}"` | căn trái 34 ký tự để cột thẳng hàng | in bảng |
| `"" if drop_identity else call.call_id` | điều kiện một dòng | `execute_call` |

## 11. AI vận dụng thế nào

- **Model không tham gia việc ghép.** Result correlation là việc **cơ học, có căn cứ** của Harness. Nếu để model "tự xoay xở" xem result nào thuộc call nào, ta lại quay về đoán.
- **Model chỉ sinh đề xuất** (tool call). Việc gắn identity cho call, giữ nó qua dispatch/executor, và dùng nó để ghi RunState đều là việc của Harness (nối với bài 07: Agent Loop, bài 08: tool request → action thật).
- **RunState là nơi lỗi ở lại.** Khi ghi nhầm, mọi iteration sau đọc state đều mang lỗi. Vì vậy ghép đúng phải xảy ra **trước** khi model nhìn thấy state.
- **Không có identity thì từ chối ghi** (`correlate_by_identity` bỏ qua result mất nhãn), chứ không quay về đoán. Thà thiếu một ô còn hơn điền sai.
- **Identity không thay cho kiểm chứng nội dung.** Nối với bài hallucination: ghép đúng chỗ chỉ giải quyết "về đúng nơi nhận", còn "có đúng nội dung/còn hiệu lực/đúng thẩm quyền" vẫn là câu hỏi riêng.
- **Giữ đúng mức chắc chắn khi chẩn đoán**: không có Trace thì `diagnose` trả `UNKNOWN`, và nói thẳng "chỉ là giả thuyết".

## 12. Ba câu tự kiểm tra (trả lời không nhìn tài liệu)

1. Hai lượt tra đều đúng mà câu trả lời vẫn sai. Chỗ hỏng nằm ở đâu?
   → Ở bước ghép result với call (result correlation). Tool chỉ lo nội dung đúng; việc result về đúng nơi nhận là việc của Harness. Ghép theo thứ tự về thì chỉ đúng khi may mắn.
2. Vì sao identity phải được tạo TRƯỚC dispatch, và vì sao vẫn chưa đủ để tin kết quả?
   → Tạo sau khi result về thì lại phải đoán. Identity chỉ chứng minh result về đúng nơi nhận, không chứng minh nội dung đúng, nguồn đúng, đủ quyền hay việc đã hoàn tất.
3. Agent trả lời nhầm đơn. Bạn được nói "chắc chắn lỗi correlation" khi nào?
   → Chỉ khi thấy identity của request/result và nơi result được ghi: result mang A chứa dữ liệu đúng của call A nhưng bị ghi vào ô của B. Nếu không có dấu vết thì chỉ là giả thuyết; nếu result A đã chứa dữ liệu sai rồi mới ghi đúng ô A thì lỗi ở chặng trước, không phải ghép.