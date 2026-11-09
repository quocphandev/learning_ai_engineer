# Bài 11: Hallucination (model trả lời rất chắc chắn, nhưng dựa vào đâu?)

## 1. Ý chính

"AI bịa" gộp **ba câu hỏi độc lập** vào một chữ. Tách ra để gọi đúng tên lỗi:

| Trục | Câu hỏi | Nằm ở đâu |
|---|---|---|
| **Confidence** | Câu này NÓI chắc đến mức nào? | giọng điệu của câu chữ |
| **Grounding** | Câu này DỰA vào căn cứ nào kiểm tra lại được? | từng claim ↔ một đoạn nguồn cụ thể |
| **Informational truth** | Câu này ĐÚNG với thực tế không (tại thời điểm hỏi)? | thực tế bên ngoài |

- Ba trục **độc lập**: nói chắc ≠ có căn cứ; có căn cứ ≠ đúng tại thời điểm hỏi; đúng ≠ kiểm chứng được.
- Giọng "chắc chắn" chỉ là **đặc điểm của output**, như cách xưng hô hay dấu chấm than. Nó không phải con số xác suất đã được đo và báo lại. Câu nói chắc không cho biết model có thật sự chắc.
- Giọng dè dặt cũng không bảo đảm gì. Giọng điệu và độ tin cậy là hai chuyện riêng.

## 2. Nguồn là ĐƯỜNG để kiểm tra, không phải CON DẤU bảo đảm

- Có link, đúng tên tài liệu, mở được: việc kiểm tra thật sự **chưa bắt đầu**.
- Phải **tách câu trả lời thành từng claim** và đặt mỗi claim cạnh đoạn nguồn tương ứng.
- Ví dụ câu A: mượn đúng con số "7 ngày" và điều kiện "chưa qua sử dụng" từ tài liệu thật, rồi gắn vào kết luận "nhận lại tiền" mà tài liệu không viết (Mục 2 nói ngược lại).
- **Grounding đo ở từng claim, không đo ở việc có link hay không.** Một câu có thể có phần bám chặt, có phần lơ lửng.

## 3. Ba câu hỏi trước khi tin một nguồn được dẫn

| Câu hỏi | Nội dung | Ví dụ trượt |
|---|---|---|
| **Relevance** | Đoạn được dẫn có THẬT SỰ nói điều claim khẳng định không? | A: đúng tài liệu, nhưng không đoạn nào nói "gửi trả giày chật được hoàn tiền" |
| **Freshness** | Có phải bản ĐANG CÓ HIỆU LỰC tại thời điểm hỏi không? | B: trích đúng từng chữ, nhưng từ bản 01/01 đã bị bản 01/07 thay |
| **Authority** | Nơi phát hành có THẨM QUYỀN quyết định chuyện này không? | C: blog review nói đúng điều đó, nhưng không phải bên ban hành chính sách |

Mỗi câu hỏi bắt một kiểu sai riêng, một nguồn có thể qua câu này mà trượt câu khác. Tất cả bằng chứng cần đều nằm trên màn hình (câu trả lời, link, trang link mở ra), không cần biết cơ chế bên trong.

## 4. Khi không có gì để mở

| Tình huống | Kết luận đúng |
|---|---|
| **Không kèm nguồn** (câu D) | Có thể đúng tình cờ, nhưng **không kiểm chứng được**. "Không có link = sai" là sai; "nó đúng rồi nên không sao" cũng bỏ qua điều quan trọng |
| **Link không mở được** / không rõ còn hiệu lực (câu F) | **Chưa kiểm chứng được**: chưa có căn cứ nói sai, cũng chưa có căn cứ coi là đúng |

- **Đúng tình cờ ≠ đã kiểm chứng.** Với quyết định có hậu quả (trả phí ship, gửi hàng, chờ tiền) cần kiểm chứng.
- Bước tiếp theo khi chưa kiểm chứng được: tìm trang chính sách trực tiếp, hỏi nhân viên, hoặc tạm chưa hành động.

## 5. Sáu câu trả lời gộp lại

| Câu | Giọng điệu | Căn cứ | Đúng thật? | Lỗi thuộc trục nào |
|---|---|---|---|---|
| A | rất chắc chắn | có link, 1 claim không bám đoạn nào (Mục 2 nói ngược) | sai | relevance |
| B | rất chắc chắn | trích đúng chữ, từ bản cũ | sai | freshness |
| C | rất chắc chắn | đoạn nói đúng, nguồn sai thẩm quyền | sai | authority |
| D | rất chắc chắn | không có nguồn | đúng (tình cờ) | không kiểm chứng được |
| E | dè dặt | từng claim bám đúng đoạn, bản hiệu lực, đúng bên | đúng | không có lỗi |
| F | rất chắc chắn | link 404 | đúng (tình cờ) | chưa kiểm chứng được |

- Nếu chỉ nhìn **giọng điệu**: tin A, B, C, D, F và nghi ngờ E (sai ba lần).
- Nếu chỉ nhìn **có link hay không**: tin A, B, C, E và gạt D (vẫn tin nhầm ba câu sai).

## 6. Giới hạn của cách nhìn này

- Chỉ dựa vào những gì sản phẩm **hiển thị**. Chỗ nào không lộ bằng chứng thì ghi "chưa biết", đừng lấp bằng suy đoán.
- Chỉ xét câu tư vấn có đúng **về mặt thông tin** không. Nếu bot nói "mình đã tạo yêu cầu đổi hàng", muốn biết hệ thống có thật sự làm không thì phải kiểm chứng bằng thứ khác (xem bài 08: tool call, observation).
- Không xét cơ chế phía sau: cách tìm, xếp hạng, chọn đoạn tài liệu; điều kiện để một dữ kiện được coi là fact dùng được; cách xây eval đo hallucination.

## 7. Ứng dụng thực tế (cùng một khung kiểm tra)

| Hệ thống | Claim hay gặp | Relevance | Freshness | Authority |
|---|---|---|---|---|
| Bot CSKH (đổi trả, bảo hành) | "được hoàn tiền trong 7 ngày" | đoạn chính sách có nói đúng không | bản chính sách hiện hành | chính cửa hàng, không phải blog/diễn đàn |
| Trợ lý nội bộ (nhân sự, nghỉ phép) | "được nghỉ 12 ngày phép" | đúng mục quy chế | quy chế mới nhất | phòng nhân sự ban hành |
| Hỏi đáp tài liệu kỹ thuật / API | "hàm này nhận tham số X" | đúng đoạn tài liệu | đúng phiên bản thư viện | tài liệu chính thức, không phải bài blog cũ |
| Pháp lý, tuân thủ | "luật quy định mức phạt Y" | điều khoản có nói không | văn bản còn hiệu lực | cơ quan ban hành |
| Tài chính, báo cáo | "doanh thu quý này là Z" | đúng dòng, đúng kỳ | kỳ báo cáo mới nhất | báo cáo chính thức |

Quy tắc chung: **quyết định có hậu quả** (tiền, pháp lý, an toàn) cần claim ở trạng thái VERIFIED, không dựa vào giọng điệu hay sự có mặt của link.

## 8. Đầu vào, đầu ra, luồng xử lý (`exp11_grounding_check.py`)

**Đầu vào:**
1. Câu trả lời của AI, đã **tách thành các claim**, mỗi claim kèm nguồn được dẫn (tài liệu + Mục, hoặc không có nguồn).
2. Kho tài liệu nguồn kèm **metadata**: bên ban hành (`issuer`), ngày hiệu lực (`effective_from`), ngày bị thay (`superseded_on`), mở được không (`reachable`).
3. Cấu hình: bên có thẩm quyền (`POLICY_OWNER`), thời điểm hỏi (`ASKED_ON`).
4. Thẩm phán relevance (`judge`): luật so khớp (fake) hoặc Gemini (real).

**Đầu ra:** với mỗi claim: `verdict` + lý do + đoạn nguồn đã dùng; với cả câu trả lời: kết luận (ĐÃ KIỂM CHỨNG / CÓ VẤN ĐỀ / CHƯA KIỂM CHỨNG ĐƯỢC); cuối cùng bảng tổng hợp ba trục.

**Luồng cho MỘT claim (`verify_claim`):**
```
có cite_doc? ──không──► UNVERIFIABLE (không có gì để mở)
   │có
tài liệu mở được? ──không──► UNVERIFIABLE (link hỏng)
   │có
judge(claim, document)  ← RELEVANCE
   ├─ not_found / Mục không tồn tại ──► UNSUPPORTED
   ├─ contradicted ───────────────────► UNSUPPORTED (Mục n nói NGƯỢC LẠI)
   └─ supported
        │
   check_freshness ──hết hiệu lực──► STALE
        │còn
   check_authority ──sai bên ban hành──► LOW_AUTHORITY
        │đúng
     VERIFIED
```
**Luồng cho CẢ câu trả lời (`overall_decision`):** mọi claim VERIFIED → ĐÃ KIỂM CHỨNG; có claim UNSUPPORTED/STALE/LOW_AUTHORITY → CÓ VẤN ĐỀ; còn lại (có UNVERIFIABLE) → CHƯA KIỂM CHỨNG ĐƯỢC.

Lưu ý: `detect_tone` chạy **tách riêng**, kết quả chỉ để hiển thị, **không dùng** để quyết định verdict. Đó là minh họa "confidence độc lập với grounding".

## 9. Ánh xạ khái niệm → code

| Khái niệm | Trong code |
|---|---|
| Confidence | `detect_tone()` (tìm từ "chắc chắn" / "không chắc"), chỉ hiển thị |
| Grounding (claim ↔ đoạn nguồn) | `verify_claim()`, trường `grounded` của `ClaimResult` |
| Relevance | `judge_relevance_rule()` / `judge_relevance_gemini()` |
| Freshness | `check_freshness()` (`effective_from`, `superseded_on` so với `ASKED_ON`) |
| Authority | `check_authority()` (`issuer` so với `POLICY_OWNER`) |
| Không có gì để mở | verdict `UNVERIFIABLE` (không cite, hoặc `reachable=False`) |
| Informational truth | nhãn `truth` trong `ANSWERS` (chỉ để so sánh; ngoài đời không có sẵn) |
| Kết luận cả câu | `overall_decision()` |

### Vai trò từng hàm

| Hàm | Vai | Làm gì |
|---|---|---|
| `claim(...)` | tạo dữ liệu | đóng gói 1 claim: text, topic, value, nguồn dẫn |
| `detect_tone` | trục confidence | đọc giọng điệu, không liên quan độ tin cậy |
| `select_sections` | hỗ trợ relevance | chỉ xét Mục claim dẫn tới (hoặc mọi Mục nếu không nêu) |
| `judge_relevance_rule` | thẩm phán (fake) | so `topic/value` của claim với `facts` từng Mục → supported / contradicted / not_found |
| `judge_relevance_gemini` | thẩm phán (real) | nhờ Gemini đọc chữ trong tài liệu, trả JSON; sai định dạng thì coi như not_found |
| `check_freshness` | kiểm tra hiệu lực | so ngày hiệu lực / ngày bị thay với thời điểm hỏi |
| `check_authority` | kiểm tra thẩm quyền | so bên phát hành với bên có thẩm quyền |
| `verify_claim` | chấm 1 claim | chạy chuỗi: có nguồn → mở được → relevance → freshness → authority |
| `overall_decision` | chấm cả câu | chỉ "đã kiểm chứng" khi MỌI claim VERIFIED |
| `print_answer_report`, `print_summary_matrix` | hiển thị | in từng câu và bảng ba trục |

## 10. Python đã học trong bài này

| Cú pháp | Nghĩa | Chỗ dùng |
|---|---|---|
| `from datetime import date`, `date(2026, 7, 1)` | kiểu ngày; so sánh bằng `<`, `<=` như số | `check_freshness` |
| `f"{d:%d/%m/%Y}"` | định dạng ngày trong f-string (`%d` ngày, `%m` tháng, `%Y` năm) | thông báo |
| `@dataclass class ClaimResult` | gói kết quả; trường có giá trị mặc định (`passage: str = ""`) phải đứng cuối | `ClaimResult` |
| dict lồng nhiều tầng | `DOCUMENTS[doc_id]["sections"][2]["facts"]` truy cập từng tầng | dữ liệu nguồn |
| khóa dict là số | `sections = {1: {...}, 2: {...}}`, truy cập bằng `sections[2]` | các Mục |
| `d.items()` trong `for number, section in ...` | duyệt cặp (khóa, giá trị) | `judge_relevance_rule` |
| `any(m in lowered for m in LIST)` | `True` nếu CÓ ÍT NHẤT MỘT phần tử thỏa điều kiện | `detect_tone` |
| `sum(1 for r in results if r.grounded)` | đếm số phần tử thỏa điều kiện | `main` |
| `{r.verdict for r in results}` | **set comprehension**: tập các giá trị không trùng | `overall_decision` |
| `verdicts == {"VERIFIED"}` | so sánh tập; `a & b` là giao của hai tập (`if verdicts & PROBLEM_VERDICTS` đúng khi có phần chung) | `overall_decision` |
| `except (A, B, C) as e` | bắt nhiều loại lỗi trong một `except` | `judge_relevance_gemini` |
| `data.get("section")` | lấy giá trị, thiếu khóa thì `None` (không lỗi) | parse JSON |
| `int("2")` → `2` | ép chuỗi thành số (LLM có thể trả `"2"` thay vì `2`) | parse JSON |
| `def f(chat=None)` + `if chat is None: from llm import chat` | tham số tùy chọn; **import trong hàm** để chỉ nạp khi cần; cho phép truyền hàm giả khi test | `judge_relevance_gemini` |
| `status = "not_found"` gán lại giữa hàm | sửa biến để các `if` phía sau dùng giá trị mới | `verify_claim` |
| `f"{'Câu':<4}{'Giọng điệu':<15}"` | căn trái từng cột để bảng thẳng hàng | `print_summary_matrix` |
| tuple trong list rồi giải nén | `for a, b, c in rows` | `print_summary_matrix` |
| `sys.argv[2].upper()` | tham số dòng lệnh thứ hai, đổi sang chữ hoa | `main` |

## 11. AI vận dụng thế nào trong bài này

- **Model chỉ sinh câu chữ.** Giọng "chắc chắn" là một phần của output, không phải số đo độ tin cậy. Vì vậy hệ thống kiểm tra **không** dùng `detect_tone` để quyết định.
- **Kiểm chứng nằm NGOÀI model**, ở lớp Harness/kiểm tra: tách câu trả lời thành claim, đối chiếu từng claim với nguồn, rồi mới kết luận. Cùng tinh thần "model đề xuất, Harness kiểm tra" ở bài 07 và 08.
- **Thẩm phán relevance có thể là chính một LLM** (`judge_relevance_gemini`). Điều này hữu ích nhưng thẩm phán cũng có thể sai, nên code có ba lớp phòng thủ: sai định dạng JSON → `not_found`; `status` lạ → `not_found`; chỉ tới Mục không tồn tại → không tin.
- **Freshness và authority không phải việc của model**: chúng đến từ **metadata của nguồn** (ngày hiệu lực, bên ban hành) do hệ thống quản lý. Model không tự biết bản nào còn hiệu lực.
- Bài tập này giả định câu trả lời đã được tách claim sẵn kèm nguồn. Ngoài đời, bước "tách claim và gắn nguồn" là một bước riêng (thường nhờ model xuất dữ liệu có cấu trúc: claim + nguồn dẫn).
- **Đơn giản hóa có chủ ý**: chế độ `fake` so khớp `topic/value` (khớp tuyệt đối), còn ngôn ngữ tự nhiên thật phức tạp hơn nhiều. Một claim VERIFIED ở mức claim vẫn có thể làm cả câu gây hiểu lầm (claim "7 ngày" ở câu A khớp Mục 2 nhưng là 7 ngày cho hàng lỗi), nên `overall_decision` đòi MỌI claim phải VERIFIED.

## 12. Ba câu tự kiểm tra (trả lời không nhìn tài liệu)

1. Vì sao câu "Chắc chắn được bạn nhé!" kèm link vẫn chưa đáng tin?
   → Giọng chắc chỉ là cách viết. Link chỉ là đường kiểm tra: phải đối chiếu từng claim với đoạn nguồn, rồi hỏi relevance, freshness, authority.
2. Câu D không có nguồn nhưng đúng. Có nên coi là ổn không?
   → Đúng tình cờ ≠ đã kiểm chứng. Với quyết định có hậu quả, cần claim có căn cứ kiểm chứng được.
3. Link mở ra trang lỗi 404. Được kết luận gì?
   → "Chưa kiểm chứng được": không có căn cứ nói sai, cũng không có căn cứ coi là đúng. Bước tiếp: tìm nguồn trực tiếp, hỏi người có thẩm quyền, hoặc tạm chưa hành động.