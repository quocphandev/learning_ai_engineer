"""Bài 07 - Agent Loop: làm, quan sát, rồi mới đi tiếp.

Cách chạy:
    python exp7_agent_loop.py fake    # 3 kịch bản có sẵn, model giả lập, KHÔNG cần API key
    python exp7_agent_loop.py real    # dùng Gemini thật làm model (cần llm.py + .env)
"""
import json
import sys
from dataclasses import dataclass, field

# Số iteration tối đa trong MỘT user turn (lan can an toàn, tránh chạy vô hạn)
MAX_ITERATIONS_PER_TURN = 6
# Số iteration liên tiếp "không có gì mới" mà Harness chịu đựng trước khi cắt run
MAX_STALLED = 2


# ---------------------------------------------------------------------------
# 1. TOOLS: "thế giới bên ngoài". Model KHÔNG bao giờ gọi trực tiếp các hàm này.
# ---------------------------------------------------------------------------
def get_shipping_status(order_id):
    # Giả lập service vận chuyển: lúc nào cũng "chưa có scan mới"
    return {"order_id": order_id, "latest_scan": None}


def get_order_info(order_id):
    # Giả lập thông tin đơn trong hệ thống cửa hàng: địa chỉ thiếu số căn hộ (apartment = None)
    return {"order_id": order_id, "address": "12 Le Loi, District 1", "apartment": None}


# Allowlist: tên action (chuỗi) -> hàm thật. Action nào không có ở đây thì Harness từ chối.
TOOLS = {
    "get_shipping_status": get_shipping_status,
    "get_order_info": get_order_info,
}
# Lưu ý: "ask_customer" và "finish" cố ý KHÔNG nằm trong TOOLS.
# Chúng không phải tool chạy ra bên ngoài, mà là đề xuất do Harness tự xử lý.


# ---------------------------------------------------------------------------
# 2. RUNSTATE: trí nhớ của Harness, được mang từ iteration này sang iteration sau
# ---------------------------------------------------------------------------
@dataclass
class RunState:
    customer_messages: list = field(default_factory=list)  # các tin nhắn khách đã gửi
    facts: dict = field(default_factory=dict)              # điều run đang TIN là đúng (đã chắt lọc)
    observations: list = field(default_factory=list)       # mọi thứ từng trả về (dữ liệu thô, như log)
    iteration_count: int = 0                               # đếm trên CẢ run, không reset mỗi turn
    stalled_count: int = 0                                 # số iteration liên tiếp không có gì mới
    hint: str = ""                                         # lời nhắc Harness gửi lại cho model


@dataclass
class TurnResult:
    status: str     # "done" | "ask_user" | "stalled" | "max_iterations"
    question: str = ""   # câu hỏi gửi khách (chỉ dùng khi status == "ask_user")


# ---------------------------------------------------------------------------
# 3. FACT VÀ TIẾN TRIỂN: biến observation thành fact, rồi hỏi "cái gì đã đổi?"
# ---------------------------------------------------------------------------
def extract_facts(source, data):
    """Chắt fact từ một observation. source cho biết observation đến từ đâu."""
    if source == "get_shipping_status":
        scan = data["latest_scan"]
        return {"shipping_status": "no_new_scan" if scan is None else f"scanned_at_{scan}"}
    if source == "get_order_info":
        return {"address_complete": data["apartment"] is not None}
    if source == "customer_reply":
        # Khách trả lời => ta biết số căn hộ => địa chỉ đã đầy đủ
        return {"apartment": data, "address_complete": True}
    return {}  # lỗi, bị từ chối...: không có fact mới


def apply_observation(state, source, data):
    """Ghi observation vào RunState và trả về những fact THỰC SỰ thay đổi."""
    new_facts = extract_facts(source, data)
    # Chỉ giữ lại fact mới hoặc fact có giá trị khác trước
    changed = {k: v for k, v in new_facts.items() if state.facts.get(k) != v}

    state.facts.update(new_facts)
    state.observations.append({"source": source, "data": data})

    if changed:
        # Có tiến triển: reset bộ đếm và xóa lời nhắc
        state.stalled_count = 0
        state.hint = ""
    else:
        # Không có gì mới: tăng bộ đếm và nhắc model đổi hướng
        state.stalled_count += 1
        state.hint = ("Bước vừa rồi không mang lại thông tin mới. ĐỪNG lặp lại. "
                      "Hãy chọn nguồn khác, hỏi khách, hoặc kết thúc.")
    return changed


def is_complete(facts):
    """Điều kiện hoàn thành do HARNESS sở hữu (không phải do model)."""
    return "shipping_status" in facts and facts.get("address_complete") is True


def decide(state):
    """Harness quyết định vòng lặp đi tiếp hay dừng. Model chỉ đề xuất."""
    if is_complete(state.facts):
        return "stop_done"
    if state.stalled_count >= MAX_STALLED:
        return "stop_stalled"
    return "continue"


# ---------------------------------------------------------------------------
# 4. AGENT LOOP (một user turn = nhiều iteration)
# ---------------------------------------------------------------------------
def log(label, text):
    print(f"   {label:<9}: {text}")


def run_turn(state, propose):
    """Chạy các iteration cho tới khi turn này kết thúc. Trả về TurnResult.

    state:   RunState dùng chung cho cả run
    propose: hàm đóng vai MODEL, nhận state và trả về proposal dạng {"action": ..., "args": {...}}
    """
    for _ in range(MAX_ITERATIONS_PER_TURN):
        state.iteration_count += 1
        print(f"\n -- iteration {state.iteration_count} --")

        # (1) MODEL đề xuất bước tiếp theo (chưa có gì được thực thi)
        proposal = propose(state)
        action, args = proposal.get("action"), proposal.get("args", {})
        log("MODEL", f"đề xuất {action} {args}")

        # (2) HARNESS kiểm tra đề xuất
        if action == "ask_customer":
            # Hỏi khách => kết thúc TURN (không phải kết thúc run), chờ khách trả lời
            log("HARNESS", "ask_customer -> dừng turn này, chờ khách trả lời")
            return TurnResult("ask_user", args.get("question", "Bạn có thể cho biết thêm chi tiết không?"))

        if action == "finish":
            if is_complete(state.facts):
                log("HARNESS", "chấp nhận finish: điều kiện hoàn thành đã đủ")
                return TurnResult("done")
            # Model nói "xong" nhưng Harness không tin: ghi nhận như một observation không có gì mới
            log("HARNESS", "TỪ CHỐI finish: điều kiện hoàn thành chưa đủ")
            changed = apply_observation(state, "harness", {"error": "finish rejected"})

        elif action in TOOLS:
            log("HARNESS", "hợp lệ -> cho thực thi")
            # (3) EXECUTOR chạy tool thật. Lỗi cũng được coi là một observation.
            try:
                data = TOOLS[action](**args)
            except Exception as error:
                data = {"error": str(error)}
            # (4) OBSERVATION: kết quả trả về
            log("OBSERVE", data)
            # (5) Harness cập nhật RunState và xem fact nào đã đổi
            changed = apply_observation(state, action, data)

        else:
            log("HARNESS", f"action lạ '{action}' -> từ chối")
            changed = apply_observation(state, "harness", {"error": "unknown action"})

        log("RUNSTATE", f"facts={state.facts} | mới={changed or 'KHÔNG CÓ GÌ MỚI'} | stalled={state.stalled_count}")

        # (6) HARNESS quyết định đi tiếp hay dừng
        decision = decide(state)
        log("DECISION", decision)
        if decision == "stop_done":
            return TurnResult("done")
        if decision == "stop_stalled":
            return TurnResult("stalled")

    return TurnResult("max_iterations")


def run_conversation(first_message, propose, get_customer_reply, reply_writer, max_turns=3):
    """Chạy cả cuộc hội thoại gồm nhiều user turn, dùng chung MỘT RunState.

    first_message:      tin nhắn đầu tiên của khách
    propose:            hàm model (giả hoặc Gemini thật)
    get_customer_reply: hàm nhận câu hỏi của bot, trả về câu trả lời của khách
    reply_writer:       hàm viết câu trả lời cuối cùng gửi khách (content uncertainty)
    max_turns:          số user turn tối đa
    """
    state = RunState(customer_messages=[first_message])
    result = TurnResult("max_iterations")

    for turn in range(1, max_turns + 1):
        print(f"\n===== USER TURN {turn}  (khách: {state.customer_messages[-1]!r}) =====")
        result = run_turn(state, propose)

        if result.status != "ask_user":
            break  # done / stalled / max_iterations: hết cuộc hội thoại

        print(f"\n BOT hỏi khách: {result.question}")
        reply = get_customer_reply(result.question)
        print(f" KHÁCH trả lời: {reply}")
        state.customer_messages.append(reply)
        # Lời khách trả lời cũng là một observation, và nó làm đổi fact
        apply_observation(state, "customer_reply", reply)

    print(f"\n>>> RUN KẾT THÚC: {result.status} | số iteration={state.iteration_count} | facts={state.facts}")
    if result.status == "done":
        print(">>> BOT TRẢ LỜI:", reply_writer(state))
    return state


# ---------------------------------------------------------------------------
# 5. CÁC MODEL. Model giả chạy theo kịch bản để bạn thấy Harness hoạt động.
# ---------------------------------------------------------------------------
def stubborn_model(state):
    """Run 1 trong bài: cứ gọi lại cùng một tool (bận rộn nhưng không tiến triển)."""
    return {"action": "get_shipping_status", "args": {"order_id": "ORD-001"}}


def smart_model(state):
    """Run 2 trong bài: biết thêm điều gì thì đổi hướng theo observation."""
    facts = state.facts
    if "shipping_status" not in facts:
        return {"action": "get_shipping_status", "args": {"order_id": "ORD-001"}}
    if "address_complete" not in facts:
        return {"action": "get_order_info", "args": {"order_id": "ORD-001"}}
    if facts["address_complete"] is False:
        return {"action": "ask_customer", "args": {"question": "Số căn hộ của bạn là bao nhiêu ạ?"}}
    return {"action": "finish", "args": {}}


def overconfident_model(state):
    """Nói 'xong rồi' quá sớm, khi Harness chưa đồng ý."""
    return {"action": "finish", "args": {}}

def hint_respecting_model(state):
    """Nghe lời nhắc của Harness: khi không rỗng thì đổi hướng."""

    if state.facts.get("address_complete") is False:
        return {"action" : "ask_customer", "args":{"question" : "Số căn hộ của bạn là bao nhiêu ạ?"}}
    
    if state.facts.get("address_complete") is True:
        return {"action" : "finish", "args":{}}

    if state.hint:
        return {"action": "get_order_info", "args": {"order_id": "ORD-001"}}
    
    return {"action": "get_shipping_status", "args": {"order_id": "ORD-001"}}


SYSTEM_PROMPT = """Bạn là "bộ não" của một agent chăm sóc khách hàng cho cửa hàng online.
Mỗi lượt bạn chỉ được ĐỀ XUẤT đúng MỘT bước tiếp theo. Bạn không tự thực thi gì cả.
Các action được phép:
- get_shipping_status(order_id)   # xem thông tin scan của đơn vị vận chuyển
- get_order_info(order_id)        # xem người nhận, địa chỉ, số căn hộ
- ask_customer(question)          # hỏi khách khi chỉ khách mới có thông tin còn thiếu
- finish()                        # khi bạn cho rằng đã đủ thông tin để trả lời khách
Quy tắc: không lặp lại bước đã không mang lại thông tin mới. Hãy chú ý "Harness hint".
Chỉ trả về MỘT đối tượng JSON: {"action": "...", "args": {...}}"""


def gemini_model(state):
    """Model thật: đưa facts, observations và hint vào prompt rồi đọc đề xuất JSON."""
    from llm import chat  # llm.py bạn đã làm ở bài 03

    user_message = (
        f"Tin nhắn của khách: {json.dumps(state.customer_messages, ensure_ascii=False)}\n"
        f"Các fact đã biết: {json.dumps(state.facts, ensure_ascii=False)}\n"
        f"Các observation: {json.dumps(state.observations, ensure_ascii=False)}\n"
        f"Harness hint: {state.hint or 'không có'}"
    )
    raw = chat(SYSTEM_PROMPT, user_message, json_mode=True)
    try:
        proposal = json.loads(raw)
    except json.JSONDecodeError:
        # Model trả sai định dạng: biến thành action lạ để Harness xử lý, không để chương trình sập
        return {"action": "__invalid__", "args": {}}
    return proposal if isinstance(proposal, dict) else {"action": "__invalid__", "args": {}}


def template_reply(state):
    """Viết câu trả lời cuối bằng mẫu cố định (dùng cho chế độ fake)."""
    return (f"Đơn ORD-001: trạng thái vận chuyển là {state.facts['shipping_status']}. "
            f"Bên mình đã ghi nhận số căn hộ của bạn ({state.facts.get('apartment', 'đã có sẵn')}).")


def gemini_reply(state):
    """Nhờ Gemini viết câu trả lời cuối (chỉ dùng các fact đã có)."""
    from llm import chat

    return chat("Bạn là nhân viên CSKH. Trả lời ngắn gọn bằng tiếng Việt, CHỈ dùng các fact được cung cấp.",
                f"Facts: {json.dumps(state.facts, ensure_ascii=False)}")


# ---------------------------------------------------------------------------
# 6. MAIN: điểm bắt đầu của chương trình
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # INPUT 1 - mode: lấy từ tham số dòng lệnh (python exp7_agent_loop.py fake | real)
    #   "fake": dùng model giả lập, chạy 3 kịch bản có sẵn, không tốn tiền API
    #   "real": dùng Gemini thật, bạn đóng vai khách trả lời khi bot hỏi
    #   sys.argv[0] là tên file, sys.argv[1] là tham số đầu tiên; không gõ gì thì mặc định "fake"
    mode = sys.argv[1] if len(sys.argv) > 1 else "fake"

    if mode == "fake":
        # INPUT 2 - question: câu khách nhắn đầu tiên, là "đề bài" cho cả run
        question = "Đơn ORD-001 của tôi đang ở đâu rồi?"

        # INPUT 3 - scripted_reply: hàm giả lập khách. Khi bot hỏi gì (tham số q),
        #   nó luôn trả lời "Căn hộ 12B". Dùng lambda (hàm một dòng, không tên) cho gọn.
        scripted_reply = lambda q: "Căn hộ 12B"

        # INPUT 4 - danh sách kịch bản: mỗi phần tử là (tiêu đề, hàm model).
        #   Cùng một vòng lặp run_conversation, chỉ đổi "bộ não" để thấy Harness xử lý khác nhau.
        scenarios = [
            ("RUN 1: model cứng đầu (bận nhưng không tiến triển)", stubborn_model),
            ("RUN 2: model thông minh (biết đổi hướng)", smart_model),
            ("RUN 3: model quá tự tin (nói 'xong' quá sớm)", overconfident_model),
            ("RUN 4: model nghe lời nhắc (được Harness cho cơ hội sửa sai)", hint_respecting_model)
        ]
        for title, model in scenarios:
            print("\n" + "#" * 70 + f"\n# {title}\n" + "#" * 70)
            run_conversation(question, model, scripted_reply, template_reply)
    else:
        # INPUT 2 - tin nhắn đầu tiên của khách (cho chạy với Gemini thật)
        question = "Đơn ORD-001 của tôi đang ở đâu rồi?"

        # INPUT 3 - get_customer_reply: khi bot hỏi, chương trình dừng lại và chờ BẠN gõ câu trả lời
        #   bằng input(). Bạn đóng vai khách hàng (ví dụ gõ "Căn hộ 12B").
        ask_real_customer = lambda q: input("(hãy trả lời với vai khách hàng) > ")

        run_conversation(question, gemini_model, ask_real_customer, gemini_reply)