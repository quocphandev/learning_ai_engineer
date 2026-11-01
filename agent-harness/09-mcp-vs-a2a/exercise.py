# Bài 09 — MCP và A2A: lấy capability về dùng hay giao việc cho Agent khác

from dataclasses import dataclass, field

# [COPY] ===== DỮ LIỆU NGHIỆP VỤ =====
ORDER_DB = {"ORD-001": {"state": "shipping"}, "ORD-010": {"state": "packing"}}
CUSTOMER_ORDERS = {"C-1": ["ORD-010"], "C-2": ["ORD-001"]}

# ===== 1. MCP SERVER: công bố capability (tool / resources / prompts) =====

"""Server CUNG CẤP capability.  Nó không quyết định ai được xem đơn nào."""
class OrderMcpServer:

    def __init__(self) -> None:
        self.connected = False

    def connect(self, api_key: str) -> bool:
        self.connected = api_key == "valid-key" # xác thực ở LỚP KẾT NỐI 
        return self.connected

    def list_capabilities(self) -> dict:
        return {
            "tools": ["get_order"],
            "resources": ["policy://shipping"],
            "prompts" : ["reply_order_status"]
        }

    def call_tool(self, name: str, arguments: dict) -> dict:
        order = ORDER_DB.get(arguments["order_id"])
        return {"order_id": arguments["order_id"], **order} if order else {"error": "order_not_found"}

# ===== 2. A2A: Warranty Agent là một Agent system ĐỘC LẬP =====
# thứ Warranty Agent CÔNG BỐ  cho bên giao
WARRANTY_CONTRACT = {
    "submitted": "đã nhận Task",
    "working" : "đang xét",
    "completed" : "đã XÉT XONG = kết quả có thể là approved hoặc rejected"
}


@dataclass
class A2ATask:
    task_id: str
    case_id: str
    state: str = "submitted"
    result: dict | None = None

class WarrantyAgent:
    """Có Harness riêng. Bên ngoài chỉ thấy lifecycle + kết quả của Task."""

    def __init__(self) ->None:
        self._tasks: dict[str, A2ATask] = {}
        self._internal_log: list[str] = []

    def send_task(self, case_id: str) -> str:
        task_id = f"task-{len(self._tasks) + 1}"
        self._tasks[task_id] = A2ATask(task_id, case_id)
        return task_id

    def get_task(self, task_id: str) -> dict:
        task = self._tasks[task_id]
        self._advance(task) # bên nhận tự làm theo cách của mình
        return {"task_id": task.task_id, "state": task.state, "result": task.result}

    def _advance(self, task: A2ATask) -> None:
        if task.state == "submitted":
            task.state = "working"
            self._internal_log.append("tra lịch sửa mua hàng, đối chiếu chính sách nội bộ")
        elif task.state == "working":
            task.state = "completed"
            task.result = {"decision": "rejected", "reason": "quá hạn bảo hành 12 tháng"}

# ===== 3. SUPPORT AGENT: host của MCP + bên giao việc của A2A =====

@dataclass
class SupportAgent:
    customer_id: str
    mcp: OrderMcpServer
    warranty: WarrantyAgent
    log: list[str] = field(default_factory=list)


    # --- Quan hệ MCP: việc chạy trong vòng xử lý của Support ---

    def handle_order_question(self, order_id: str) -> str:
        proposal = {"tool": "get_order", "arguments": {"order_id": order_id}} # model đề xuất
        self.log.append(f"model đề xuất: {proposal}")

        if not self.mcp.connected:
            return "Chưa kết nối được hệ thống đơn hàng."
        # Kết nối đã xác thực <> khách hàng được phép xem -> HOST tự kiểm tra nghiệp vụ
        if order_id not in CUSTOMER_ORDERS.get(self.customer_id, []):
            self.log.append("host: TỪ CHỐI, khác hàng không sở hữu đơn (MCP không kiểm tra thay)")
            return "Xin lỗi, mình không tìm thấy đơn này trong tài khoản của bạn."
        # host cho chạy
        result = self.mcp.call_tool(proposal["tool"], proposal["arguments"])
        self.log.append(f"kết quả trả về vòng xử lý của Support: {result}")
        # Support tự quyết
        return f"Đơn {order_id} hiện đang ở trạng thái '{result['state']}'."

    # --- Quan hệ A2A: Việc chạy trong Harness của Warranty Agent ---
    def handoff_warranty(self, case_id: str, read_contract: bool) -> str:
        task_id = self.warranty.send_task(case_id)
        self.log.append(f"giao Task {task_id} cho Warranty Agent")
        while True:
            task = self.warranty.get_task(task_id)
            self.log.append(f"lifecycle: {task['state']} ({WARRANTY_CONTRACT[task['state']]})")
            if task['state'] == "completed":
                break

        if not read_contract:  # SAI: tự gán nghĩa cho completed
            return "Hàng của bạn đã được đổi rồi ạ!"
        decision = task["result"]["decision"] # DÚNG: đọc kết quả theo contract
        if decision == "approved":
            return "Hồ sơ bảo hành đã được duyệt, shop sẽ liên hệ đổi hàng."
        return f"Hồ sơ đã được xét: chưa được duyệt ({task['result']['reason']})."

# ===== 4. NHẬN DIỆN QUAN HỆ: dựa vào quan hệ, không dựa vào "có model phía sau" =====
INTEGRATIONS = [
    {"name": "Tool tra đơn", "result_returns_to_my_loop": True, "other_side_decides_how": False, "has_model_behind": True},
    {"name": "Server tóm tắt tài liệu", "result_returns_to_my_loop": True, "other_side_decides_how": False, "has_model_behind": True},
    {"name": "Warranty Agent", "result_returns_to_my_loop": False, "other_side_decides_how": True, "has_model_behind": True},
]

def classify(integration: dict) -> str:
    if integration["other_side_decides_how"]:
        return "A2A - giao task cho Agent system tự vận hành"
    return "MCP - lấy capaility về dùng trong vòng xử lý của mình"

# [COPY] ===== CHẠY =====
def run(title: str, agent: SupportAgent, action) -> None:
    agent.log.clear()
    reply = action()
    print(f"\n{title}")
    for line in agent.log:
        print(f"   · {line}")
    print(f"   💬 Khách nhận: {reply}")

def main() -> None:
    mcp = OrderMcpServer()
    print("MCP connect:", mcp.connect("valid-key"), "| capabilities:", mcp.list_capabilities())
    warranty = WarrantyAgent()

    owner = SupportAgent("C-2", mcp, warranty)
    stranger = SupportAgent("C-1", mcp, warranty)

    run("1. MCP: chủ đơn hỏi ORD-001", owner, lambda: owner.handle_order_question("ORD-001"))
    run("2. MCP: người KHÁC hỏi ORD-001 (kết nối OK, nghiệp vụ không cho)", stranger,
        lambda: stranger.handle_order_question("ORD-001"))
    run("3. A2A: tự gán nghĩa cho 'completed'", owner,
        lambda: owner.handoff_warranty("WRN-042", read_contract=False))
    run("4. A2A: đọc kết quả theo contract", owner,
        lambda: owner.handoff_warranty("WRN-042", read_contract=True))

    print("\n5. Nhận diện quan hệ:")
    for integration in INTEGRATIONS:
        print(f"   · {integration['name']:<26} (model phía sau: {integration['has_model_behind']!s:<5}) → {classify(integration)}")
    print("\nSupport KHÔNG thấy nội bộ Warranty Agent: chỉ có lifecycle + result trong log ở trên.")


if __name__ == "__main__":
    main()