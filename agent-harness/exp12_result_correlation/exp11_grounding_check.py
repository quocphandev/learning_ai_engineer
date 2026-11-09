"""Kết quả đúng nhưng gán nhầm chỗ vẫn thành sai: result correlation, call_id, RunState update.

Hai câu hỏi KHÁC NHAU:
  (1) Result này có đúng NỘI DUNG không?      -> việc của tool
  (2) Result này có về đúng NƠI NHẬN không?   -> việc của result correlation (Harness)

Cách chạy (không cần API key, vì model không tham gia việc ghép):
    python exp_result_correlation.py          # chạy cả 4 kịch bản
    python exp_result_correlation.py 1        # chỉ kịch bản 1
Kịch bản: 1 = ghép theo thứ tự về (SAI) | 2 = ghép theo identity (ĐÚNG)
          3 = hai lượt tra cùng chặng bay  | 4 = chẩn đoán nguyên nhân khi trả lời nhầm đối tượng
"""
import asyncio
import itertools
import sys
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# 1. DỮ LIỆU GIẢ LẬP
# ---------------------------------------------------------------------------
ORDERS = {
    "ORD-001": {"order_id": "ORD-001", "detail": "đang giao, dự kiến ngày mai tới"},
    "ORD-002": {"order_id": "ORD-002", "detail": "đã hủy, đang hoàn tiền"},
    "ORD-010": {"order_id": "ORD-010", "detail": "đang đóng gói"},
}

# Hai lượt tra cùng chặng bay trả về NỘI DUNG GIỐNG HỆT nhau (cùng tuyến, giờ, giá)
FLIGHT_RESULT = {"route": "HAN-DAD", "departure": "07:00", "price": 1200000}

# Độ trễ giả lập (giây) của từng "ô": quyết định result nào về TRƯỚC.
# ORD-002 nhanh hơn ORD-001 nên result của ORD-002 luôn về trước (đúng như trong bài).
LATENCY_BY_SLOT = {"ORD-001": 0.20, "ORD-002": 0.05, "ORD-010": 0.10,
                   "flight_1_passenger": 0.20, "flight_2_passengers": 0.05}


# ---------------------------------------------------------------------------
# 2. CALL, RESULT VÀ IDENTITY
# ---------------------------------------------------------------------------
@dataclass
class ToolCall:
    call_id: str        # identity ổn định, được cấp TRƯỚC khi call rời Harness
    tool_name: str
    arguments: dict
    slot: str           # ô trong RunState mà kết quả của call này SẼ được ghi vào


@dataclass
class ToolResult:
    call_id: str        # executor trả lại đúng nhãn của call vừa chạy ("" nghĩa là nhãn bị rơi mất)
    content: dict


class CallFactory:
    """Nơi DUY NHẤT tạo call, và luôn cấp identity ngay lúc tạo (trước dispatch)."""

    def __init__(self):
        self._counter = itertools.count(1)   # bộ đếm 1, 2, 3, ... dùng chung cho mọi call của factory

    def make_call(self, tool_name, arguments, slot):
        call_id = f"call_{next(self._counter):03d}"      # call_001, call_002, ...
        return ToolCall(call_id, tool_name, arguments, slot)


# ---------------------------------------------------------------------------
# 3. RUNSTATE VÀ TRACE
# ---------------------------------------------------------------------------
@dataclass
class RunState:
    slots: dict = field(default_factory=dict)       # ô -> nội dung đã ghi (thứ các bước sau dựa vào)


@dataclass
class Trace:
    """Dấu vết để chẩn đoán: không có nó thì chỉ nghi ngờ được, không kết luận được."""
    requests: dict = field(default_factory=dict)    # call_id -> arguments lúc GỬI ĐI
    results: list = field(default_factory=list)     # (call_id mang theo, content), theo thứ tự VỀ
    writes: list = field(default_factory=list)      # (ô được ghi, call_id của result, content)


# ---------------------------------------------------------------------------
# 4. EXECUTOR: chạy call, trả result kèm đúng identity của call đó
# ---------------------------------------------------------------------------
async def execute_call(call, wrong_content_for=None, drop_identity=False):
    """Giả lập executor chạy bất đồng bộ.

    wrong_content_for: dict call_id -> order_id, mô phỏng lỗi nguồn dữ liệu trả nhầm đơn
    drop_identity:     mô phỏng executor làm rơi mất nhãn identity
    """
    await asyncio.sleep(LATENCY_BY_SLOT.get(call.slot, 0.1))     # mỗi call xong ở thời điểm riêng

    if call.tool_name == "get_order":
        wanted = (wrong_content_for or {}).get(call.call_id, call.arguments["order_id"])
        content = ORDERS[wanted]
    else:
        content = FLIGHT_RESULT
    return ToolResult("" if drop_identity else call.call_id, content)


async def dispatch_and_collect(calls, trace, **executor_options):
    """Dispatch mọi call cùng lúc, trả về các result THEO THỨ TỰ CHÚNG VỀ (không phải thứ tự gửi)."""
    for call in calls:
        if not call.call_id:
            raise ValueError("call chưa có identity: không được phép dispatch")   # identity phải có TRƯỚC
        trace.requests[call.call_id] = call.arguments

    tasks = [asyncio.create_task(execute_call(call, **executor_options)) for call in calls]
    arrived = []
    for finished in asyncio.as_completed(tasks):     # as_completed: cái nào xong trước trả về trước
        result = await finished
        arrived.append(result)
        trace.results.append((result.call_id, result.content))
    return arrived


# ---------------------------------------------------------------------------
# 5. HAI CÁCH GHÉP RESULT VỚI CALL
# ---------------------------------------------------------------------------
def write_slot(state, trace, slot, result):
    state.slots[slot] = result.content
    trace.writes.append((slot, result.call_id, result.content))


def correlate_by_position(calls, results, state, trace):
    """SAI: result thứ n thuộc call thứ n. Phụ thuộc thứ tự về, mà thứ tự đó không ai kiểm soát."""
    for call, result in zip(calls, results):
        write_slot(state, trace, call.slot, result)


def correlate_by_identity(calls, results, state, trace):
    """ĐÚNG: tìm call theo identity mà result mang theo. Không có identity khớp thì KHÔNG đoán."""
    pending = {call.call_id: call for call in calls}      # sổ "đang chờ": identity -> call
    for result in results:
        call = pending.pop(result.call_id, None)           # lấy call ra khỏi sổ (None nếu không có)
        if call is None:
            print(f"   ! result mang identity {result.call_id!r} không khớp call nào đang chờ "
                  f"-> KHÔNG ghi (không đoán)")
            continue
        write_slot(state, trace, call.slot, result)


def correlate_by_content(calls, result):
    """Lối tắt 'nhìn nội dung': tìm call có tuyến bay trùng với result. Dễ mơ hồ."""
    return [call for call in calls if call.arguments.get("route") == result.content["route"]]


# ---------------------------------------------------------------------------
# 6. CHẨN ĐOÁN: trả lời nhầm đối tượng thì lỗi nằm ở chặng nào?
# ---------------------------------------------------------------------------
def diagnose(trace, asked_order_ids):
    """Chỉ kết luận khi CÓ DẤU VẾT. Trả về (nhãn nguyên nhân, giải thích)."""
    if not trace.requests or not trace.writes:
        return "UNKNOWN", "không có identity của request/result và không biết result ghi vào đâu: chỉ là giả thuyết"

    for call_id, arguments in trace.requests.items():              # chặng 1: gửi đúng đơn khách hỏi chưa?
        if arguments["order_id"] not in asked_order_ids:
            return "WRONG_REQUEST", f"{call_id} tra {arguments['order_id']} nhưng khách không hỏi đơn này"

    for slot, result_call_id, content in trace.writes:             # chặng 2: nội dung, chặng 3: ghép
        requested = trace.requests.get(result_call_id)
        if requested is None:
            return "UNKNOWN", f"result mang identity {result_call_id!r} không khớp request nào"
        if content["order_id"] != requested["order_id"]:
            return "CONTENT_ERROR", (f"result mang {result_call_id} (call tra {requested['order_id']}) nhưng chứa "
                                     f"dữ liệu {content['order_id']}: bước ghép đúng theo identity, lỗi ở chặng trước")
        if slot != requested["order_id"]:
            return "CORRELATION_ERROR", (f"result của {result_call_id} (đúng nội dung {content['order_id']}) "
                                         f"bị ghi vào ô {slot}")
    return "NO_PROBLEM_FOUND", "request, nội dung và vị trí ghi đều khớp"


# ---------------------------------------------------------------------------
# 7. IN KẾT QUẢ
# ---------------------------------------------------------------------------
def print_arrival(results):
    names = [f"{r.call_id or '(mất nhãn)'}→{r.content.get('order_id', r.content.get('route'))}" for r in results]
    print("   thứ tự result VỀ  :", "  ,  ".join(names))


def print_state_and_answer(state):
    print("   RunState sau khi ghi:")
    for slot, content in state.slots.items():
        correct = content.get("order_id") == slot
        print(f"     ô {slot:<8}: {content['detail']:<34} {'✔ đúng chỗ' if correct else '✘ GHI NHẦM CHỖ'}")
    print("   Câu trả lời gửi khách:")
    for slot, content in state.slots.items():
        print(f"     - {slot}: {content['detail']}")


def make_two_order_calls(factory, first="ORD-001", second="ORD-002"):
    return [factory.make_call("get_order", {"order_id": first}, first),
            factory.make_call("get_order", {"order_id": second}, second)]


# ---------------------------------------------------------------------------
# 8. CÁC KỊCH BẢN
# ---------------------------------------------------------------------------
def scenario_positional():
    print("\n" + "=" * 74 + "\nKỊCH BẢN 1: ghép theo THỨ TỰ VỀ (cách sai)\n" + "=" * 74)
    state, trace = RunState(), Trace()
    calls = make_two_order_calls(CallFactory())
    results = asyncio.run(dispatch_and_collect(calls, trace))
    print("   thứ tự call GỬI   :", ", ".join(f"{c.call_id}→{c.slot}" for c in calls))
    print_arrival(results)
    correlate_by_position(calls, results, state, trace)
    print_state_and_answer(state)
    print("   >>> Tool tra đúng, dữ liệu đúng, nhưng RunState bị điền CHÉO nên câu trả lời sai.")


def scenario_identity():
    print("\n" + "=" * 74 + "\nKỊCH BẢN 2: ghép theo IDENTITY (cách đúng)\n" + "=" * 74)
    state, trace = RunState(), Trace()
    calls = make_two_order_calls(CallFactory())
    results = asyncio.run(dispatch_and_collect(calls, trace))
    print("   thứ tự call GỬI   :", ", ".join(f"{c.call_id}→{c.slot}" for c in calls))
    print_arrival(results)
    correlate_by_identity(calls, results, state, trace)
    print_state_and_answer(state)
    print("   >>> Result về thứ tự nào cũng không còn quan trọng: mỗi result tự mang 'địa chỉ' của call.")

    print("\n   --- Thử bỏ identity: executor làm rơi mất nhãn ---")
    state2, trace2 = RunState(), Trace()
    calls2 = make_two_order_calls(CallFactory())
    results2 = asyncio.run(dispatch_and_collect(calls2, trace2, drop_identity=True))
    correlate_by_identity(calls2, results2, state2, trace2)
    print(f"   số ô đã ghi: {len(state2.slots)}  (mất identity thì từ chối ghép, thay vì quay về đoán)")

    print("\n   --- Thử bỏ cấp identity trước dispatch ---")
    try:
        bad_call = ToolCall("", "get_order", {"order_id": "ORD-001"}, "ORD-001")
        asyncio.run(dispatch_and_collect([bad_call], Trace()))
    except ValueError as error:
        print(f"   bị chặn: {error}")


def scenario_flights():
    print("\n" + "=" * 74 + "\nKỊCH BẢN 3: hai lượt tra CÙNG chặng bay, nội dung giống hệt nhau\n" + "=" * 74)
    state, trace = RunState(), Trace()
    factory = CallFactory()
    calls = [
        factory.make_call("search_flights", {"route": "HAN-DAD", "passengers": 1}, "flight_1_passenger"),
        factory.make_call("search_flights", {"route": "HAN-DAD", "passengers": 2}, "flight_2_passengers"),
    ]
    results = asyncio.run(dispatch_and_collect(calls, trace))
    print_arrival(results)

    print("\n   Cách 'nhìn nội dung' (ghép theo tuyến bay):")
    for result in results:
        candidates = correlate_by_content(calls, result)
        print(f"     result mang {result.call_id} -> {len(candidates)} call khớp: "
              f"{[c.call_id for c in candidates]}  => MƠ HỒ, không biết ghi vào ô nào")

    print("\n   Cách identity:")
    pending = {call.call_id: call for call in calls}
    for result in results:
        call = pending[result.call_id]
        print(f"     result mang {result.call_id} -> ghi vào ô '{call.slot}'  (chắc chắn, dựa vào nhãn)")


def scenario_diagnosis():
    print("\n" + "=" * 74 + "\nKỊCH BẢN 4: cùng triệu chứng 'trả lời nhầm đơn', bốn nguyên nhân khác nhau\n" + "=" * 74)
    asked = ["ORD-001", "ORD-002"]

    # (a) lỗi ghép: dùng cách ghép theo thứ tự về
    state, trace = RunState(), Trace()
    calls = make_two_order_calls(CallFactory())
    results = asyncio.run(dispatch_and_collect(calls, trace))
    correlate_by_position(calls, results, state, trace)
    print("\n (a) Harness ghép theo thứ tự về:")
    print("     ", diagnose(trace, asked))

    # (b) lỗi nội dung: identity đúng, nhưng nguồn dữ liệu trả nhầm đơn cho call_001
    state, trace = RunState(), Trace()
    calls = make_two_order_calls(CallFactory())
    results = asyncio.run(dispatch_and_collect(calls, trace, wrong_content_for={"call_001": "ORD-002"}))
    correlate_by_identity(calls, results, state, trace)
    print("\n (b) Ghép đúng theo identity, nhưng nguồn trả nhầm dữ liệu:")
    print("     ", diagnose(trace, asked))

    # (c) lỗi request: call được gửi đi với mã đơn sai ngay từ đầu
    state, trace = RunState(), Trace()
    calls = make_two_order_calls(CallFactory(), first="ORD-010", second="ORD-002")
    results = asyncio.run(dispatch_and_collect(calls, trace))
    correlate_by_identity(calls, results, state, trace)
    print("\n (c) Call được gửi đi với mã đơn sai:")
    print("     ", diagnose(trace, asked))

    # (d) không có dấu vết: chỉ thấy câu trả lời sai
    print("\n (d) Không có identity/trace (chỉ thấy câu trả lời sai từ bên ngoài):")
    print("     ", diagnose(Trace(), asked))

    print("\n   >>> Cùng một triệu chứng, chỉ có dấu vết mới phân biệt được 'ghép sai' với các nguyên nhân khác.")


# ---------------------------------------------------------------------------
# 9. MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # INPUT 1 - selected: số kịch bản muốn chạy ("1".."4"); không gõ gì thì chạy cả 4.
    #   Lấy từ sys.argv[1] (tham số dòng lệnh đầu tiên sau tên file).
    selected = sys.argv[1] if len(sys.argv) > 1 else "all"

    # INPUT 2 - scenarios: bảng "số kịch bản -> hàm chạy kịch bản đó".
    #   Hàm cũng là giá trị nên bỏ vào dict được, rồi gọi bằng scenarios[key]().
    scenarios = {"1": scenario_positional, "2": scenario_identity,
                 "3": scenario_flights, "4": scenario_diagnosis}

    # INPUT 3 - LATENCY_BY_SLOT (khai báo ở đầu file): độ trễ giả lập của từng call.
    #   Đổi con số này để đổi result nào về trước, và xem cách ghép theo thứ tự có còn "may mắn đúng" không.
    for key, scenario in scenarios.items():
        if selected in ("all", key):
            scenario()