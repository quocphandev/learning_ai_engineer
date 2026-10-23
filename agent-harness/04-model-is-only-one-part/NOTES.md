# Bài 04 — Model chỉ là một phần của hệ thống Agent

## 1. Câu cốt lõi
> **Model đề xuất. Phần còn lại của hệ thống quyết định đề xuất đó có thành hành động thật hay không, và hành động đó chạm vào đâu.**

- Model chỉ **viết ra chữ**. Output có 2 dạng:
  - Câu trả lời text
  - **Đề xuất gọi tool**, ví dụ `{"type": "tool_call", "tool": "lookup_order", ...}`
- Đề xuất gọi tool **vẫn chỉ là dữ liệu**: model không mở kết nối, không đọc database.
- Agent làm đúng → "model giỏi" chỉ là **một** trong nhiều lý do.
- Agent làm sai → "model kém" chỉ là **một** trong nhiều khả năng.

## 2. Bốn vùng trách nhiệm
Chia theo **trách nhiệm**, không phải theo số service. Một sản phẩm có thể gộp hoặc tách các vùng.

| Vùng | LÀM | KHÔNG làm |
|---|---|---|
| **Model** | Tạo output hoặc proposal | Không tự thực thi |
| **Agent configuration** | Instructions, tool descriptions, parameters/defaults, capability declaration → **định hình proposal** | Không cấp quyền, không enforce, khai báo ≠ làm được |
| **Harness/runtime** | Chuẩn bị input, kiểm tra output, **quyết định dispatch**, giữ state, điều khiển lượt chạy | Không tự nghĩ câu trả lời |
| **Environment** | Dữ liệu, file, API, service. Trả dữ liệu, chịu tác động (effect) | Không mặc nhiên quyết định permission |

**Chỉ Harness/runtime** quyết định một đề xuất có thành lời gọi thật hay không.

### Ví dụ ghi nhớ: tổng đài văn phòng
- Lễ tân = **Model** (nghĩ xem nên gọi ai)
- Danh bạ "Kho hàng: máy lẻ 204" = **Configuration**
- Tổng đài nối máy = **Harness/runtime**
- Dây điện thoại đã kéo tới kho = **Integration**
- Cái kho thật = **Environment**

→ Danh bạ có số nhưng **dây chưa kéo** thì cuộc gọi không tới đâu, dù lễ tân vẫn có thể nói "tôi gọi rồi".

## 3. Mô tả tool ≠ kết nối tới dữ liệu
Muốn agent tra được dữ liệu, cần đủ **3 thứ**:
1. **Configuration** mô tả tool → model biết mà đề xuất
2. **Integration** → code thật nối tới dữ liệu
3. **Runtime** cho phép và thật sự dispatch

Thiếu một thứ là không tra được, dù câu trả lời nghe vẫn rất tự tin.

## 4. Đổi sang model mạnh hơn

| Có thể giúp | Không thể giúp |
|---|---|
| Hiểu câu hỏi tốt hơn | Tạo ra integration còn thiếu |
| Chọn tool đúng hơn | Làm dữ liệu cũ mới lên |
| Viết đúng định dạng hơn | Cấp quyền mà runtime đang chặn |

- Đổi model **không chỉ đổi câu chữ**: model mới có thể đề xuất khác, và cả lượt chạy rẽ sang hướng khác.
- "Đổi model thì chạy được" là **manh mối**, chưa phải **kết luận** "model cũ kém". Có thể chỉ là mô tả tool chưa hợp với cách model cũ hiểu.

## 5. Bảng tra: triệu chứng → vùng hỏi trước

| Triệu chứng | Hỏi trước | Cần bằng chứng |
|---|---|---|
| Không thấy lượt tra nào | Còn **3 khả năng**: (1) model không đề xuất → Model/Config; (2) có đề xuất nhưng không dispatch → Runtime; (3) không có integration | Model có đề xuất không? Có được dispatch không? |
| Nói "đã kiểm tra" nhưng sai | **Harness/runtime**: đã có dispatch và observation thật chưa? | Bản ghi lượt chạy, không phải lời của agent |
| Có tra thật nhưng dữ liệu sai hoặc cũ | **Environment** trước, sau đó **Harness** (kết quả có được đưa đúng vào input không) | Dữ liệu gốc |
| Sai giọng điệu, định dạng, cách hiểu | **Model + Configuration** | Instructions, defaults |
| Làm được việc bị cấm, hoặc bị chặn việc được làm | **Harness/runtime**, không phải capability declaration | Logic dispatch |

## 6. Nguyên tắc vàng
> **Thiếu bằng chứng thì chưa kết luận root cause.**

- Chọn vùng hỏi trước = **đặt giả thuyết**, chưa phải kết luận.
- "Không thấy" chưa phải "không có".
- "Mình đã kiểm tra" là **output của model**, chưa phải bằng chứng.
- Đôi khi câu trả lời đúng nhất là: *"Có 3 khả năng, chưa đủ dữ kiện để chọn."*

### Câu hỏi đặt trước khi đổi model
1. Agent đang tự thuật, hay đã có lượt tra thật?
2. Nếu có tra: dữ liệu từ đâu, còn mới không?
3. Nếu không thấy tra: khả năng nào còn bỏ ngỏ?
4. Sản phẩm có cho mình bằng chứng để chọn không?

## 7. Áp dụng khi build agent (từ bài tập `exercise.py`)
- Mỗi vùng là **hàm hoặc class riêng**: dễ biết lỗi nằm ở đâu.
- Mọi model có **cùng hình dạng** `(system, prompt, json_mode) -> str` → thay model không phải sửa harness.
- Có **một hàm quyết định dispatch duy nhất** (`decide_dispatch`), kiểm tra:
  - `allowed_tools` → có được **phép** không
  - `integrations` → có **dây nối** không
  - Hàm này **không nhìn vào config**.
- **Ghi trace** mọi sự kiện, mỗi sự kiện gắn `zone`:
  - `proposal` (model) ≠ `observation` (environment)
  - Có proposal mà không có observation → đề xuất không được dispatch
- Harness **đối chiếu lời tự thuật với trace** → gắn cờ `unverified_claim`.
- Lỗi thì báo lại cho model bằng dòng `HARNESS: ...`, không crash.
- `max_steps` để vòng lặp luôn dừng.
- Debug theo kiểu **giữ nguyên mọi thứ, đổi đúng 1 vùng**, rồi quan sát.

| Trách nhiệm runtime | Hàm trong code |
|---|---|
| Chuẩn bị input | `build_input()` |
| Kiểm tra output | `parse_model_output()` |
| Quyết định dispatch | `decide_dispatch()` |
| Giữ state | biến `notes` |
| Điều khiển lượt chạy | `run_agent()` + `max_steps` |

---

## 8. Python học được trong bài

| Cú pháp | Ý nghĩa |
|---|---|
| `snake_case` / `PascalCase` / `UPPER_CASE` / `_name` | Hàm, biến, file / class / hằng số / nội bộ |
| `d.get("k")`, `d.get("k", mặc_định)` | Lấy giá trị an toàn, không crash khi thiếu khoá |
| `A or B or ""` | Lấy giá trị đầu tiên "có nghĩa" |
| `{"a": 1, **other}` | Trải các cặp của dict khác vào dict mới |
| `f"...{x}..."`, `{x:.0f}`, `{x:<18}` | F-string, định dạng số, căn lề |
| `@dataclass` + `field(default_factory=dict)` | Hộp dữ liệu. Không dùng `= {}` vì mọi hộp sẽ dùng chung một dict |
| `Callable[[dict], dict]` | Kiểu "một hàm" |
| `model = fake_model` (không có `()`) | Hàm cũng là giá trị: gán, truyền được |
| `set()`, `{"a"}` | Set. Lưu ý `{}` là **dict** rỗng |
| `[x for x in xs if ...]`, `{k: v for ...}` | List / dict comprehension |
| `any(...)`, `"\n".join(...)` | Có ít nhất 1 cái đúng / nối chuỗi |
| `try / except Loại:` / `finally:` | Bắt lỗi / phần luôn chạy |
| `json.loads` ↔ `json.dumps(..., ensure_ascii=False)` | Chuỗi JSON ↔ dict, giữ tiếng Việt |
| `isinstance(x, dict)` | Kiểm tra kiểu |
| `re.compile`, `re.search`, `.group()` | Regex |
| `return a, b` → `a, b = f()` | Trả về nhiều giá trị, tách tuple |
| `x[-1]`, `s[5:]`, `s[:200]` | Phần tử cuối, slicing |
| `range(1, n + 1)`, `enumerate(xs, start=1)` | Vòng lặp. `range` không lấy số cuối |
| `continue` / `return` trong vòng lặp | Sang lượt kế / thoát cả hàm |
| `global x` | Gán lại biến cấp module từ trong hàm |
| `A if điều_kiện else B` | If-else viết trên một dòng |
| `datetime.strptime(s, "%Y-%m-%d %H:%M")`, `.total_seconds()` | Đọc chuỗi ngày giờ, đổi khoảng thời gian ra giây |
|