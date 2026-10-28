"""Bài 08 - Từ tool request tới action thực tế.
Pipeline 5 chặng: Proposal -> Gate -> Dispatch -> Executor/service -> Observation

Gate gôm nhiều lớp: parse -> schema -> semantic -> authorization/approval.

Cách chay:
    python exp8_tool_popeline.py fake
    python exp8_tool_popeline.py real
"""

import json
import re
import sys
from dataclasses import dataclass, field

# 1. CONTRACT CỦA TOOL: tool tên gì, cần tham số nào, kiểu gì, định dạng ra sao
TOOL_SCHEMAS = {
    "get_order" : {
        "order_id" : {"type": str, "pattern": r"ORD-\d{3}"},
    },
    "send_customer_notification": {
        "order_id": {"type": str, "pattern": r"ORD-\d{3}"},
        "message": {"type": str, "pattern": r".{1,200}"},
    }
}

# Tool có effect ra bên ngoài hệ thống (gửi tin, ghi dữ liệu ...) thì cần người duyệt
TOOLS_WITH_EXTERNAL_EFFECT = {"send_customer_notification"}

# 2. SERVICE GIẢ LẬP: "thế gới bên ngoài" mà EXCUTOR làm việc cùng

class ServiceError(Exception):
    pass

ORDER_DB = {
    "ORD-001": {"state": "shipping"},
    "ORD-010": {"state": "packing"},
    # ORD-020 cố ý KHÔNG có trong DB (dữ liệu cũ) để mô phỏng order_not_found
}

CUSTOMER_ORDER = {
    "C-1": ["ORD-010", "ORD-020"],
    "C-2": ["ORD-001"],
}

def execute_get_order(arguments):
    order = ORDER_DB.get(arguments["order_id"])
    if order is None:
        raise ServiceError("order_not_found")
    return {"order_id": arguments["order_id"], "state": order["state"]}


def execute_send_notification(arguments):
    # Service chỉ trả "accepted" = ĐÃ TIẾP NHẬN yêu cầu gửi tin
    # Nó không nói đã tới điện thoai khách (không có "delivered")
    return {"status": "accepted", "message_id": "msg-001"}


# Bảng dispatch: tên tool -> executor phụ trách tool đó

EXECUTORS = {
    "get_order": execute_get_order,
    "send_customer_notification": execute_send_notification,
}

# 3. CONTEXT VÀ TRACE
@dataclass
class RunContext:
    customer_id: str
    looked_up_orders: list = field(default_factory=list)


@dataclass
class Trace:
    """Dấu vết của một tool request:  mỗi chặng ghi lại bằng chứng riêng."""
    stages: dict = field(default_factory=dict)
    gate_layers: list=field(default_factory=list)

    def record(self, stage, status, detail):
        self.stages[stage] = (status, detail)
    
    def add_layer(self, layer, status, detail):
        selt.gate_layers.append((layer, status, detail))
        

# 4. CÁC LỚP CỦA GATE: mỗi lớp trả lời MỘT câu hỏi riêng

def parse_tool_request(row_output):
    """Lớp parse: output của model có đọc được thành một tool call không?"""
    try:
        data = json.loads(row_output)
    except json.JSONDecodeError as error:
        return None, f"Không đọc được JSON ({error.msg})"

    if not isinstance(data, dict) or "name" not in data or not isinstance(data.get("arguments"), dict):
        return None, "thiếu 'name' or 'arguments"

    if data['name'] not in TOOL_SCHEMAS:
        return None, f"tool '{data['name']}' không tồn tại trong schema"    
    return data, "đọc được tool call"


def validate_schema(tool_name, arguments):
    """Lớp schema: arguments có đúng MẪU (đủ trường, đúng kiểu, đúng định dạng) không?
    Lưu ý: schema KHÔNG biết đơn có tồn tại hay có đúng người không."""
    schema = TOOL_SCHEMAS[tool_name]
    for field_name, rule in schema.items():
        if field_name not in arguments:
            return False, f"thiếu trường '{field_name}'"
        value = arguments[field_name]
        if not isinstance(value, rule["type"]):
            return False, f"'{field_name}' phải là {rule['type'].__name__}, nhận {type(value).__name__}"
        if not re.fullmatch(rule["pattern"], value, re.DOTALL):
            return False, f"'{field_name}'={value!r} sai định dạng"
    extra = set(arguments) - set(schema)
    if extra:
        return False, f"có trường thừa: {sorted(extra)}"
    return True, "đúng mẫu schema"
 
 
def validate_semantics(tool_name, arguments, context):
    """Lớp semantic: giá trị có HỢP LÝ trong ngữ cảnh nghiệp vụ không?"""
    if tool_name == "send_customer_notification":
        # Chỉ được báo cho khách về đơn mà run này đã tra thành công
        if arguments["order_id"] not in context.looked_up_orders:
            return False, f"{arguments['order_id']} chưa được tra trong run này"
    return True, "hợp lý trong ngữ cảnh"
 
 
def authorize(tool_name, arguments, context, approve_fn):
    """Lớp authorization/approval. Trả về (kết quả, chi tiết), kết quả là allowed | denied | pending."""
    owned_orders = CUSTOMER_ORDERS.get(context.customer_id, [])
    if arguments["order_id"] not in owned_orders:
        return "denied", f"khách {context.customer_id} không có quyền với {arguments['order_id']}"
 
    if tool_name in TOOLS_WITH_EXTERNAL_EFFECT:
        if approve_fn is None:
            return "pending", "tool có effect ra ngoài, đang CHỜ người duyệt"
        if not approve_fn(tool_name, arguments):
            return "denied", "người duyệt đã từ chối"
        return "allowed", "đã được người duyệt"
    return "allowed", "khách có quyền với đơn này"

# ---------------------------------------------------------------------------
# 5. PIPELINE: Proposal -> Gate -> Dispatch -> Executor -> Observation
# ---------------------------------------------------------------------------
def handle_tool_request(raw_output, context, approve_fn=None):
    """Đưa một tool request đi qua 5 chặng và trả về Trace (dấu vết từng chặng).
 
    raw_output: đoạn text MODEL đã sinh ra (chưa có gì được thực thi)
    context:    RunContext (khách là ai, đã tra đơn nào)
    approve_fn: hàm người duyệt (tool_name, arguments) -> True/False; None nghĩa là chưa có ai duyệt
    """
    trace = Trace()
 
    # Chặng 1 - PROPOSAL: model đã sinh ra output này
    trace.record("proposal", "có", raw_output)
 
    # Chặng 2 - GATE: Harness kiểm tra lần lượt từng lớp, lớp nào không qua thì dừng ngay
    request, detail = parse_tool_request(raw_output)
    trace.add_layer("parse", "đạt" if request else "KHÔNG đạt", detail)
    if request is None:
        trace.record("gate", "từ chối", f"dừng ở lớp parse: {detail}")
        return trace
    tool_name, arguments = request["name"], request["arguments"]
 
    ok, detail = validate_schema(tool_name, arguments)
    trace.add_layer("schema", "đạt" if ok else "KHÔNG đạt", detail)
    if not ok:
        trace.record("gate", "từ chối", f"dừng ở lớp schema: {detail}")
        return trace
 
    ok, detail = validate_semantics(tool_name, arguments, context)
    trace.add_layer("semantic", "đạt" if ok else "KHÔNG đạt", detail)
    if not ok:
        trace.record("gate", "từ chối", f"dừng ở lớp semantic: {detail}")
        return trace
 
    verdict, detail = authorize(tool_name, arguments, context, approve_fn)
    trace.add_layer("authorization", verdict, detail)
    if verdict == "denied":
        trace.record("gate", "từ chối", f"dừng ở lớp authorization: {detail}")
        return trace
    if verdict == "pending":
        trace.record("gate", "chờ duyệt", detail)    # chưa dispatch, chưa có action nào
        return trace
    trace.record("gate", "cho phép", "đã qua mọi lớp cần thiết")
 
    # Chặng 3 - DISPATCH: chuyển request tới đúng executor phụ trách tool
    executor = EXECUTORS[tool_name]
    trace.record("dispatch", "đã chuyển", f"-> {executor.__name__}")
 
    # Chặng 4 - EXECUTOR: chặng ĐẦU TIÊN mà action thật có thể xảy ra
    try:
        result = executor(arguments)
        trace.record("executor", "ok", result)
        observation = {"tool": tool_name, "status": result.get("status", "ok"), "result": result}
    except ServiceError as error:
        trace.record("executor", "lỗi", str(error))
        observation = {"tool": tool_name, "status": "error", "error": str(error)}
 
    # Chặng 5 - OBSERVATION: thứ Harness thật sự nhận lại (lỗi cũng là observation)
    trace.record("observation", observation["status"], observation)
    if tool_name == "get_order" and observation["status"] == "ok":
        context.looked_up_orders.append(arguments["order_id"])   # ghi nhớ cho các lớp sau
    return trace
 
# ---------------------------------------------------------------------------
# 6. ĐỌC DẤU VẾT: chặng nào có bằng chứng, chặng nào chưa
# ---------------------------------------------------------------------------
STAGE_LABELS = [
    ("proposal", "1. Proposal"),
    ("gate", "2. Gate decision"),
    ("dispatch", "3. Dispatch"),
    ("executor", "4. Executor/service"),
    ("observation", "5. Observation"),
]
 
 
def print_report(trace):
    for key, label in STAGE_LABELS:
        if key in trace.stages:
            status, detail = trace.stages[key]
            print(f"   {label:<22}: {status}")
            if key == "gate":
                for layer, layer_status, layer_detail in trace.gate_layers:
                    print(f"        - lớp {layer:<13} {layer_status:<10} {layer_detail}")
        else:
            print(f"   {label:<22}: CHƯA CÓ DẤU VẾT -> chưa có bằng chứng về chặng này")
 
 
def conclude(trace):
    """Kết luận CHỈ dựa trên bằng chứng đang có, không suy đoán thêm."""
    gate_status = trace.stages.get("gate", ("", ""))[0]
    if gate_status == "từ chối":
        return "Bị chặn ở gate, chưa có action nào xảy ra. " + trace.stages["gate"][1]
    if gate_status == "chờ duyệt":
        return "Đang chờ duyệt: chưa dispatch, chưa có action nào xảy ra."
 
    status, observation = trace.stages["observation"]
    if status == "accepted":
        return ("Service đã TIẾP NHẬN yêu cầu gửi tin. CHƯA có bằng chứng khách đã nhận được "
                "(không có dấu vết của chặng 'tin tới điện thoại khách').")
    if status == "ok":
        return f"Đã thực hiện xong và có kết quả thật: {observation['result']}"
    return f"Request đã đi trọn đường tới service và nhận lỗi '{observation['error']}' (vẫn là observation có giá trị)."


# ---------------------------------------------------------------------------
# 7. MODEL: giả lập bằng văn bản có sẵn, hoặc Gemini thật
# ---------------------------------------------------------------------------
def make_tool_call(name, arguments):
    """Tạo đoạn output giống thứ model sinh ra khi 'gọi tool' (chỉ là TEXT, chưa chạy gì)."""
    return json.dumps({"type": "tool_call", "name": name, "arguments": arguments}, ensure_ascii=False)
 
 
SYSTEM_PROMPT = """Bạn là "bộ não" của agent chăm sóc khách hàng. Bạn KHÔNG tự thực thi gì, chỉ đề xuất tool call.
Các tool: 
- get_order(order_id)                         # order_id dạng ORD-123
- send_customer_notification(order_id, message)
Chỉ trả về MỘT đối tượng JSON: {"type": "tool_call", "name": "...", "arguments": {...}}"""
 
 
def gemini_propose_tool_request(customer_message):
    from llm import chat  # llm.py bạn đã làm ở bài 03
    return chat(SYSTEM_PROMPT, f"Tin nhắn của khách: {customer_message}", json_mode=True)

# ---------------------------------------------------------------------------
# 8. MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # INPUT 1 - mode: lấy từ tham số dòng lệnh (python exp8_tool_pipeline.py fake | real)
    #   "fake": 8 kịch bản có sẵn, không tốn API
    #   "real": Gemini sinh tool request thật, bạn đóng vai người duyệt
    mode = sys.argv[1] if len(sys.argv) > 1 else "fake"
 
    if mode == "fake":
        # INPUT 2 - contexts: mỗi khách có một RunContext riêng (khách C-2 sở hữu ORD-001,
        #   khách C-1 sở hữu ORD-010 và ORD-020). looked_up_orders sẽ được ghi nhớ giữa các kịch bản.
        contexts = {"C-1": RunContext("C-1"), "C-2": RunContext("C-2")}
 
        # INPUT 3 - approve_yes: giả lập "người duyệt" luôn bấm Đồng ý. Truyền None nghĩa là
        #   chưa có ai duyệt (request sẽ nằm ở trạng thái 'chờ duyệt').
        approve_yes = lambda tool_name, arguments: True
 
        # INPUT 4 - scenarios: mỗi phần tử là (tiêu đề, id khách, output do model sinh ra, hàm duyệt).
        #   Cột thứ 3 là TEXT model sinh ra; pipeline phải tự kiểm tra nó, không tin tuyệt đối.
        notify = lambda order_id: make_tool_call(
            "send_customer_notification", {"order_id": order_id, "message": "Đơn của bạn đang được giao"})
        scenarios = [
            ("A. Tra đơn hợp lệ, đi trọn 5 chặng", "C-2",
             make_tool_call("get_order", {"order_id": "ORD-001"}), None),
            ("B. Gửi thông báo nhưng CHƯA có ai duyệt", "C-2", notify("ORD-001"), None),
            ("C. Gửi thông báo ĐÃ được duyệt (service trả 'accepted')", "C-2", notify("ORD-001"), approve_yes),
            ("D. Gửi thông báo cho đơn chưa từng tra (sai ngữ cảnh)", "C-2", notify("ORD-010"), approve_yes),
            ("E. JSON bị cụt, không parse được", "C-1",
             '{"type": "tool_call", "name": "get_order", "arguments": {"order_id": "ORD-010"', None),
            ("F. Sai schema: order_id là số", "C-1", make_tool_call("get_order", {"order_id": 1}), None),
            ("G. Đúng schema nhưng đơn của khách khác (khách C-1 gõ nhầm ORD-001)", "C-1",
             make_tool_call("get_order", {"order_id": "ORD-001"}), None),
            ("H. Đúng schema, đúng quyền, nhưng service báo order_not_found", "C-1",
             make_tool_call("get_order", {"order_id": "ORD-020"}), None),
        ]
        for title, customer_id, raw_output, approver in scenarios:
            print("\n" + "=" * 72 + f"\n{title}\n" + "=" * 72)
            print("   model sinh ra:", raw_output)
            trace = handle_tool_request(raw_output, contexts[customer_id], approver)
            print_report(trace)
            print("   >>> KẾT LUẬN:", conclude(trace))
    else:
        # INPUT 2 - tin nhắn của khách gửi cho Gemini thật
        customer_message = "Đơn ORD-001 của mình tới đâu rồi? Có gì mới thì báo mình nhé."
        context = RunContext("C-2")
 
        # INPUT 3 - approve_by_human: khi tool cần duyệt, chương trình dừng lại hỏi BẠN (y/n)
        approve_by_human = lambda tool_name, arguments: input(
            f"Duyệt cho chạy {tool_name} {arguments}? (y/n) > ").strip().lower() == "y"
 
        for step in range(1, 4):   # cho model tối đa 3 lần đề xuất
            raw_output = gemini_propose_tool_request(customer_message)
            print(f"\n--- đề xuất {step} ---\n   model sinh ra:", raw_output)
            trace = handle_tool_request(raw_output, context, approve_by_human)
            print_report(trace)
            print("   >>> KẾT LUẬN:", conclude(trace))
            customer_message += f"\n[Harness] Kết quả bước {step}: {trace.stages.get('observation', trace.stages['gate'])[1]}"