# Bài 07: Agent Loop (làm, quan sát, rồi mới đi tiếp)

## 1. Ý chính

**Bận rộn ≠ tiến triển.** Một agent có thể chạy rất nhiều vòng, log dài thêm liên tục, nhưng vẫn đứng yên.
Câu hỏi duy nhất cần nhớ: **"Vòng vừa rồi đổi được gì?"**

## 2. Một vòng (iteration) gồm 6 bước

```
Model đề xuất → Harness kiểm tra → Executor chạy → Observation trả về
              → Harness cập nhật RunState → Harness quyết định (tiếp / đổi hướng / chờ / hỏi / dừng)
```

- **Model chỉ đề xuất (proposal)**, chưa có gì được thực thi.
- **Harness giữ quyền cuối cùng.** Model nói "xong rồi" cũng chỉ là một đề xuất nữa, Harness tự kiểm tra điều kiện hoàn thành.
- **Lỗi cũng là observation**, không phải "thất bại không có giá trị". Nó có thể đổi bước tiếp theo.

## 3. Ba khái niệm hay bị trộn

| Khái niệm     | Nghĩa                                 | Ví dụ ORD-001                        |
| ------------- | ------------------------------------- | ------------------------------------ |
| **Iteration** | 1 nhịp đề xuất → action → observation | model gọi `get_order_info`           |
| **User turn** | 1 lượt người dùng gửi, nhận trả lời   | khách nhắn 1 câu, bot trả 1 câu      |
| **RunState**  | trạng thái Harness giữ cho cả run     | "chưa có scan, địa chỉ thiếu căn hộ" |

- Một user turn chứa **nhiều** iteration. Giao diện chỉ thấy turn, còn tiến triển hay giậm chân nằm ở iteration.
- Không có RunState thì iteration sau không biết iteration trước tìm ra gì.
- `iteration_count` đếm trên **cả run**, không reset mỗi turn.
- `ask_customer` kết thúc **turn**, không kết thúc **run**. RunState vẫn sống để turn sau dùng tiếp.
- Lời khách trả lời cũng là một observation (nó làm đổi fact).

## 4. Tiêu chí "tiến triển"

Observation mới có làm đổi ít nhất MỘT trong ba thứ không?

1. Một **fact** mà run đang dựa vào.
2. **Lựa chọn kế tiếp** hợp lý (trước là A, giờ nên là B).
3. **Khoảng cách tới completion condition.**

- Không đổi gì → vòng đó chỉ tốn thời gian và tiền.
- Đừng đếm số lần gọi model, số lần gọi tool, số dòng "đang xử lý...". Đó chỉ đo hoạt động, không đo tiến triển.
- Một lần **đọc** dữ liệu (không có hiệu ứng ra bên ngoài) vẫn là tiến triển nếu nó làm hệ thống biết thêm điều đáng kể.
- Gọi lại cùng tool, cùng input, khi chưa có gì xảy ra giữa hai lần → gần như chắc chắn nhận lại observation cũ.
- Trong code mình chỉ đo tiêu chí 1 (fact đổi) cho gọn. Đây là đơn giản hóa có chủ ý.

## 5. Khi một vòng không mang lại gì mới, Harness có 4 hướng

1. **Đổi hướng**: tìm nguồn dữ liệu khác.
2. **Chờ event**: đợi tới khi có gì đó thực sự thay đổi (khác với "bấm tải lại mỗi 10 giây").
3. **Hỏi người dùng**: khi thông tin còn thiếu nằm ở phía họ.
4. **Dừng**: không còn hướng hợp lý.

Lặp nguyên xi là lựa chọn tệ nhất. Model có thể đề xuất bất kỳ hướng nào, nhưng chọn hướng nào là việc của Harness.

## 6. Plan, Reflection, ReAct đứng ở đâu

- **Plan**: một đề xuất về trình tự, viết trước khi có dữ liệu thật, nên có thể phải sửa ngay sau observation đầu. Có plan ≠ đang tiến triển.
- **Reflection**: một lượt model tự đánh giá hoặc đề xuất lại. "Tôi đã kiểm tra" từ model vẫn chỉ là đánh giá của model, chưa phải verification.
- **ReAct**: cách mô tả nhịp xen kẽ reasoning, action, observation. Không đòi hệ thống phải lộ private reasoning.
- Cả ba nằm **bên trong** vòng lặp, không thay được câu hỏi "observation vừa rồi đổi được gì?".

## 6b. Đánh giá sản phẩm mình không thấy bên trong

Tách hai phần: **phần thấy được** (các lần gọi tool, câu hỏi gửi lại) và **phần chưa biết** (số iteration, RunState, proposal bị chặn). Đừng tự điền phần chưa biết bằng suy đoán.

## 7. Ánh xạ khái niệm → code (`exp7_agent_loop.py`)

| Khái niệm                         | Trong code                                                                                        |
| --------------------------------- | ------------------------------------------------------------------------------------------------- |
| RunState                          | `@dataclass class RunState` (`facts`, `observations`, `iteration_count`, `stalled_count`, `hint`) |
| Model đề xuất                     | `propose(state)` (hàm model được truyền vào)                                                      |
| Allowlist                         | `TOOLS = {...}` (cố ý không chứa `ask_customer` và `finish`)                                      |
| Harness kiểm tra                  | chuỗi `if / elif / else` trong `run_turn`                                                         |
| Executor                          | `TOOLS[action](**args)`                                                                           |
| Observation                       | biến `data`                                                                                       |
| Cập nhật RunState + đo tiến triển | `apply_observation()` (trả về `changed`)                                                          |
| Completion condition              | `is_complete(facts)` (do Harness sở hữu)                                                          |
| Harness quyết định                | `decide(state)` → `stop_done` / `stop_stalled` / `continue`                                       |
| Lan can an toàn                   | `MAX_ITERATIONS_PER_TURN`, `MAX_STALLED`                                                          |
| Lời nhắc Harness gửi model        | `state.hint`                                                                                      |

**Ba quyền từ chối của Harness:**

| Model đề xuất                 | Harness làm gì                               |
| ----------------------------- | -------------------------------------------- |
| `finish` khi chưa đủ fact     | từ chối, ghi như observation không có gì mới |
| action không có trong `TOOLS` | từ chối (`unknown action`)                   |
| lặp mãi không có gì mới       | cắt run (`stop_stalled`)                     |

## 8. Bài học từ kịch bản `hint_respecting_model`

- Bản "ngây thơ" chỉ nhìn `hint` (rỗng → shipping, có chữ → order_info) **vẫn bị cắt**.
  Lý do: nghe lời nhắc đúng 1 lần, rồi hint bị xóa nên model quên ngay.
- **Hint chỉ là lời nhắc ngắn hạn. Quyết định tốt phải dựa trên RunState (fact).**
- Bản sửa kiểm tra theo thứ tự: fact trước, hint sau:
  1. `address_complete is False` → `ask_customer`
  2. `address_complete is True` → `finish`
  3. `state.hint` không rỗng → `get_order_info`
  4. còn lại → `get_shipping_status`

## 9. Python đã học trong bài này

| Cú pháp                               | Nghĩa                                                                                                            | Chỗ dùng                 |
| ------------------------------------- | ---------------------------------------------------------------------------------------------------------------- | ------------------------ |
| `@dataclass`                          | decorator tự sinh `__init__` từ các dòng `tên: kiểu = giá trị`                                                   | `RunState`, `TurnResult` |
| `field(default_factory=list)`         | giá trị mặc định riêng cho từng đối tượng (bắt buộc với list/dict, nếu viết `= []` thì mọi đối tượng dùng chung) | `RunState`               |
| `x: int`                              | type hint, chỉ để người đọc, Python không ép                                                                     | các dataclass            |
| `{k: v for k, v in d.items() if ...}` | dict comprehension: tạo dict mới bằng cách lọc                                                                   | `apply_observation`      |
| `.items()`                            | trả các cặp (khóa, giá trị)                                                                                      | `apply_observation`      |
| `d.get(k)` / `d.get(k, default)`      | lấy giá trị, thiếu khóa thì `None` / default                                                                     | nhiều nơi                |
| `d.update(other)`                     | gộp dict khác vào                                                                                                | `apply_observation`      |
| `lst.append(x)`                       | thêm vào cuối list                                                                                               | `observations`           |
| sửa đối tượng trong hàm               | `state.x += 1` sửa trực tiếp, không cần `return state`                                                           | `apply_observation`      |
| `a, b = x, y`                         | gán nhiều biến cùng lúc (tuple unpacking)                                                                        | `run_turn`               |
| `f(**d)`                              | giải nén dict thành tham số có tên                                                                               | `TOOLS[action](**args)`  |
| `for _ in range(n)`                   | `_` = biến không dùng tới                                                                                        | `run_turn`               |
| `return` sớm                          | thoát cả hàm lẫn vòng lặp                                                                                        | `decide`, `run_turn`     |
| `is None`, `is True`                  | so sánh đúng giá trị đặc biệt (không dùng `==`)                                                                  | `is_complete`            |
| hàm là tham số                        | truyền `propose`, `get_customer_reply`... vào để đổi hành vi mà không sửa vòng lặp (dependency injection)        | `run_conversation`       |
| `lambda q: "abc"`                     | hàm một dòng, không có tên                                                                                       | `main`                   |
| `{x!r}` trong f-string                | hiển thị kèm dấu nháy (repr)                                                                                     | `print`                  |
| `try / except Exception as e`         | bắt lỗi, `str(e)` đổi thành chuỗi                                                                                | executor                 |
| `sys.argv`                            | list tham số dòng lệnh (`[0]` là tên file)                                                                       | `main`                   |
| `a if cond else b`                    | điều kiện một dòng                                                                                               | `mode`, `parse`          |
| `if __name__ == "__main__":`          | chỉ chạy khi chạy trực tiếp file                                                                                 | `main`                   |

## 10. Ba câu tự kiểm tra (trả lời không nhìn tài liệu)

1. Vì sao `finish` của model bị Harness từ chối vẫn được tính là một iteration?
   → Vì nó đi qua đủ nhịp (đề xuất → kiểm tra → observation "từ chối"), nhưng không có fact mới nên `stalled_count` tăng.
2. `iteration_count` khác số user turn ở chỗ nào, và vì sao RunState phải tồn tại giữa hai turn?
   → 1 turn chứa nhiều iteration; RunState giữ fact để turn sau không bắt đầu lại từ đầu.
3. Một run có 50 dòng log vẫn có thể đứng yên. Đo điều đó bằng gì?
   → Hỏi mỗi iteration: fact có đổi không, lựa chọn kế tiếp có đổi không, có gần completion hơn không (code: `changed`, `stalled_count`).
