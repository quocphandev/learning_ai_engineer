"""Bài 13 - Hợp lệ chưa phải là giấy phép: validation, principal, authorization, approval, execution gate.

Bốn câu hỏi RIÊNG BIỆT trước khi một tool call có side effect được chạy:
    1. Dữ liệu có hợp lệ không?          -> validation
    2. Principal này có quyền không?     -> authorization (principal + action + resource + scope)
    3. Yêu cầu đã được duyệt chưa?       -> approval (chỉ khi policy yêu cầu)
    4. Có được thực thi không?           -> execution gate, đặt TRƯỚC dispatch, fail closed

Cách chạy (không cần API key, vì gate là việc của Harness chứ không phải của model):
    python exp13_execution_gate.py        # chạy cả 7 kịch bản
    python exp13_execution_gate.py 3      # chỉ kịch bản 3
"""
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime


# ---------------------------------------------------------------------------
# 1. DỮ LIỆU GIẢ LẬP CỦA NỀN TẢNG (hai cửa hàng: Mộc Trà và Lá Xanh)
# ---------------------------------------------------------------------------
ORDERS = {
    "ORD-001": {"shop": "la_xanh", "total": 520000},      # đơn thuộc cửa hàng Lá Xanh
    "ORD-002": {"shop": "la_xanh", "total": 400000},
}

CUSTOMERS = {
    # channel_preference chỉ cho biết NẾU được gửi thì dùng kênh nào; KHÔNG phải sự đồng ý nhận quảng cáo
    "cus-01": {"shop": "la_xanh", "channel_preference": "sms", "marketing_consent": False},
    "cus-02": {"shop": "la_xanh", "channel_preference": "sms", "marketing_consent": True},
}

REFUND_REASONS = ("damaged_item", "wrong_item", "late_delivery", "duplicate_charge")
APPROVAL_THRESHOLD = 300000        # policy: hoàn tiền TRÊN mức này cần quản lý duyệt


# ---------------------------------------------------------------------------
# 2. PRINCIPAL, GRANT (quyền được cấp) và SESSION (nguồn đã xác thực)
# ---------------------------------------------------------------------------
@dataclass
class Principal:
    principal_id: str
    kind: str       # "user" | "service_account"
    org: str        # tổ chức mà principal thuộc về


@dataclass
class Grant:
    """Một quyền được cấp: được làm `action` trên tài nguyên của `org`, trong giới hạn nhất định."""
    action: str
    org: str
    max_amount: int = 0             # 0 nghĩa là không áp dụng giới hạn số tiền
    allowed_reasons: tuple = ()     # rỗng nghĩa là không giới hạn lý do


PRINCIPALS = {
    "ops.minhanh": Principal("ops.minhanh", "user", "moc_tra"),             # nhân viên Mộc Trà
    "ops.view_lx": Principal("ops.view_lx", "user", "la_xanh"),             # Lá Xanh, chỉ được xem
    "ops.hoa": Principal("ops.hoa", "user", "la_xanh"),                     # Lá Xanh, hoàn tới 500k
    "ops.tam": Principal("ops.tam", "user", "la_xanh"),                     # Lá Xanh, hoàn tới 300k
    "manager.lx": Principal("manager.lx", "user", "la_xanh"),               # quản lý Lá Xanh
    "svc.reconcile": Principal("svc.reconcile", "service_account", "la_xanh"),   # job đối soát ban đêm
    "svc.marketing": Principal("svc.marketing", "service_account", "la_xanh"),   # chiến dịch marketing
}

GRANTS = {
    "ops.minhanh": [Grant("refund", "moc_tra", 500000)],
    "ops.view_lx": [Grant("view_order", "la_xanh")],
    "ops.hoa": [Grant("refund", "la_xanh", 500000)],
    "ops.tam": [Grant("refund", "la_xanh", 300000)],
    "manager.lx": [Grant("approve_refund", "la_xanh", 1000000)],
    "svc.reconcile": [Grant("refund", "la_xanh", 500000, ("duplicate_charge",))],   # chỉ hoàn phần tiền trùng
    "svc.marketing": [Grant("send_marketing", "la_xanh")],
}

# SESSIONS là nguồn ĐÃ XÁC THỰC: token đăng nhập -> principal. Đây là nơi Harness bind principal.
SESSIONS = {
    "sess-minhanh": "ops.minhanh", "sess-view": "ops.view_lx", "sess-hoa": "ops.hoa", "sess-tam": "ops.tam",
    "sess-manager": "manager.lx", "sess-reconcile": "svc.reconcile", "sess-marketing": "svc.marketing",
}

# APPROVALS: bản ghi duyệt. Nó chỉ chứng minh ĐÚNG những gì được ghi trong đó.
APPROVALS = {
    "APR-7731": {"approved_by": "manager.lx", "action": "refund", "resource": "ORD-001",
                 "max_amount": 450000, "expires_at": datetime(2026, 11, 16, 18, 0)},
}

TOOL_TO_ACTION = {"refund_order": "refund", "send_marketing_sms": "send_marketing"}

# Schema: field -> (kiểu, regex định dạng hoặc None)
TOOL_SCHEMAS = {
    "refund_order": {"order_id": (str, r"ORD-\d{3}"), "amount": (int, None),
                     "currency": (str, r"VND"), "reason": (str, None)},
    "send_marketing_sms": {"customer_id": (str, r"cus-\d{2}"), "phone": (str, r"0\d{9}"),
                           "message": (str, r".{1,160}")},
}


# ---------------------------------------------------------------------------
# 3. KẾT QUẢ CỦA GATE
# ---------------------------------------------------------------------------
@dataclass
class GateDecision:
    allowed: bool
    failed_step: str = ""
    reason: str = ""
    steps: list = field(default_factory=list)       # [(bước, "đạt"/"KHÔNG đạt", chi tiết)]


def record_pass(steps, step, detail):
    steps.append((step, "đạt", detail))


def deny(steps, step, reason):
    """Từ chối: ghi lại bước thất bại. Đây là chỗ 'fail closed': thiếu căn cứ thì dừng."""
    steps.append((step, "KHÔNG đạt", reason))
    return GateDecision(False, step, reason, steps)


# ---------------------------------------------------------------------------
# 4. CÁC BƯỚC CỦA GATE
# ---------------------------------------------------------------------------
def bind_principal(session_token):
    """Bước 1: principal lấy từ SESSION đã xác thực, KHÔNG bao giờ từ payload do model ghi."""
    principal_id = SESSIONS.get(session_token)
    if principal_id is None:
        return None
    return PRINCIPALS[principal_id]


def validate(tool_call):
    """Bước 2: dữ liệu có đúng hình thức và constraint đã khai báo không? (chưa nói gì về QUYỀN)"""
    schema = TOOL_SCHEMAS.get(tool_call.get("tool"))
    if schema is None:
        return False, f"tool {tool_call.get('tool')!r} không tồn tại"
    for field_name, (field_type, pattern) in schema.items():
        if field_name not in tool_call:
            return False, f"thiếu field '{field_name}'"
        value = tool_call[field_name]
        if not isinstance(value, field_type):
            return False, f"'{field_name}' sai kiểu"
        if pattern and not re.fullmatch(pattern, value, re.DOTALL):
            return False, f"'{field_name}' sai định dạng"
    if tool_call["tool"] == "refund_order":
        order = ORDERS.get(tool_call["order_id"])
        if order is None:
            return False, "đơn không tồn tại"
        if not 0 < tool_call["amount"] <= order["total"]:
            return False, "số tiền phải dương và không vượt giá trị đơn"
        if tool_call["reason"] not in REFUND_REASONS:
            return False, "lý do hoàn tiền không nằm trong danh sách cho phép"
    return True, "dữ liệu đúng hình thức và constraint"


def resolve_resource(tool_call):
    """Tài nguyên bị tác động và tổ chức sở hữu nó (lấy từ dữ liệu của hệ thống, không từ model)."""
    if tool_call["tool"] == "refund_order":
        return {"id": tool_call["order_id"], "org": ORDERS[tool_call["order_id"]]["shop"]}
    customer = CUSTOMERS[tool_call["customer_id"]]
    return {"id": tool_call["customer_id"], "org": customer["shop"], "customer": customer}


def authorize(principal, action, resource, tool_call):
    """Bước 3: trả lời CÂU HỎI BỐN VẾ: principal này làm action này, trên resource này, trong scope này không?"""
    grants = [g for g in GRANTS.get(principal.principal_id, []) if g.action == action]
    if not grants:                                                                       # vế ACTION
        return False, f"{principal.principal_id} không được cấp quyền '{action}'"
    grant = next((g for g in grants if g.org == resource["org"]), None)
    if grant is None:                                                                    # vế RESOURCE
        return False, (f"{resource['id']} thuộc tổ chức '{resource['org']}', "
                       f"ngoài phạm vi của {principal.principal_id}")
    amount = tool_call.get("amount", 0)
    if grant.max_amount and amount > grant.max_amount:                                   # vế SCOPE (số tiền)
        return False, f"{amount:,}đ vượt giới hạn {grant.max_amount:,}đ của {principal.principal_id}"
    if grant.allowed_reasons and tool_call.get("reason") not in grant.allowed_reasons:   # vế SCOPE (lý do)
        return False, f"lý do '{tool_call.get('reason')}' ngoài phạm vi {grant.allowed_reasons}"
    if action == "send_marketing" and not resource["customer"]["marketing_consent"]:
        # "ưu tiên SMS" chỉ là policy input chọn kênh, KHÔNG phải căn cứ cho phép gửi quảng cáo
        return False, "thiếu căn cứ cho phép gửi marketing (chưa có consent); 'ưu tiên SMS' chỉ chọn kênh"
    return True, f"{principal.principal_id} có quyền '{action}' trên {resource['id']} trong phạm vi được cấp"


def requires_approval(action, tool_call):
    """Approval chỉ cần khi POLICY quy định (không phải mọi tool call đều cần người duyệt)."""
    return action == "refund" and tool_call["amount"] > APPROVAL_THRESHOLD


def check_approval(approval_id, action, resource, tool_call, now):
    """Bước 4: approval là một CĂN CỨ đem ra đối chiếu, không phải tấm vé thay cho việc đối chiếu."""
    if not approval_id:
        return False, f"policy yêu cầu approval (> {APPROVAL_THRESHOLD:,}đ) nhưng không có approval"
    approval = APPROVALS.get(approval_id)
    if approval is None:
        return False, f"không tìm thấy approval {approval_id}"
    if approval["action"] != action or approval["resource"] != resource["id"]:
        return False, f"{approval_id} duyệt '{approval['action']}' cho {approval['resource']}, không khớp yêu cầu này"
    if tool_call["amount"] > approval["max_amount"]:
        return False, f"{tool_call['amount']:,}đ vượt mức đã duyệt {approval['max_amount']:,}đ"
    if now >= approval["expires_at"]:
        return False, f"{approval_id} đã hết hạn lúc {approval['expires_at']:%H:%M}"
    approver_grants = [g for g in GRANTS.get(approval["approved_by"], [])
                       if g.action == "approve_refund" and g.org == resource["org"]]
    if not approver_grants:
        return False, f"{approval['approved_by']} không có thẩm quyền duyệt cho tổ chức '{resource['org']}'"
    return True, f"{approval_id} khớp action, resource, giới hạn, còn hạn, do người có thẩm quyền duyệt"


def execution_gate(tool_call, session_token, approval_id=None, now=None):
    """EXECUTION GATE: gom mọi kết luận và quyết định có được dispatch hay không.
    Fail closed: thiếu bất kỳ căn cứ bắt buộc nào thì từ chối."""
    steps = []

    principal = bind_principal(session_token)                      # (1) bind principal từ nguồn đã xác thực
    if principal is None:
        return deny(steps, "bind_principal", "không xác định được principal từ session")
    ignored = sorted(set(tool_call) - {"tool"} - set(TOOL_SCHEMAS.get(tool_call.get("tool"), {})))
    note = f" | bỏ qua field model tự ghi: {ignored}" if ignored else ""
    record_pass(steps, "bind_principal", f"session -> {principal.principal_id} ({principal.org}){note}")

    ok, detail = validate(tool_call)                                # (2) validation
    if not ok:
        return deny(steps, "validation", detail)
    record_pass(steps, "validation", detail)

    action = TOOL_TO_ACTION[tool_call["tool"]]
    resource = resolve_resource(tool_call)
    ok, detail = authorize(principal, action, resource, tool_call)  # (3) authorization (bốn vế)
    if not ok:
        return deny(steps, "authorization", detail)
    record_pass(steps, "authorization", detail)

    if requires_approval(action, tool_call):                        # (4) approval, chỉ khi policy yêu cầu
        ok, detail = check_approval(approval_id, action, resource, tool_call, now)
        if not ok:
            return deny(steps, "approval", detail)
        record_pass(steps, "approval", detail)
    else:
        record_pass(steps, "approval", "policy không yêu cầu approval cho yêu cầu này")

    return GateDecision(True, "", "đủ căn cứ để dispatch", steps)   # (5) chỉ khi đủ căn cứ


# ---------------------------------------------------------------------------
# 5. DISPATCH: lúc lệnh RỜI KHỎI application. Từ đây side effect đã có thể xảy ra.
# ---------------------------------------------------------------------------
EFFECT_LOG = []         # các side effect đã THỰC SỰ xảy ra (tiền đã đi, tin đã gửi)


def dispatch(tool_call):
    if tool_call["tool"] == "refund_order":
        EFFECT_LOG.append(f"HOÀN TIỀN {tool_call['amount']:,}đ cho {tool_call['order_id']}")
    else:
        EFFECT_LOG.append(f"GỬI SMS marketing tới {tool_call['customer_id']}")


def run_through_gate(tool_call, session_token, approval_id=None, now=None):
    """Luồng ĐÚNG: gate quyết định TRƯỚC, chỉ dispatch khi được phép."""
    decision = execution_gate(tool_call, session_token, approval_id, now)
    if decision.allowed:
        dispatch(tool_call)
    return decision


def run_gate_after_dispatch(tool_call, session_token, approval_id=None, now=None):
    """Luồng SAI: dispatch trước, kiểm tra sau. Gate vẫn 'đúng' nhưng effect đã xảy ra rồi."""
    dispatch(tool_call)
    return execution_gate(tool_call, session_token, approval_id, now)


# ---------------------------------------------------------------------------
# 6. IN KẾT QUẢ
# ---------------------------------------------------------------------------
def print_decision(title, decision, dispatched_before=False):
    print(f"\n -- {title}")
    for step, status, detail in decision.steps:
        print(f"      {step:<15} {status:<10} {detail}")
    if decision.allowed:
        print("      >>> CHO PHÉP dispatch")
    elif dispatched_before:
        print(f"      >>> gate kết luận TỪ CHỐI ở bước '{decision.failed_step}', nhưng lệnh ĐÃ dispatch từ trước!")
    else:
        print(f"      >>> TỪ CHỐI ở bước '{decision.failed_step}' -> không dispatch")


def refund(order_id="ORD-001", amount=450000, reason="damaged_item", **extra_fields):
    """Tạo tool call hoàn tiền giống hệt payload model đề xuất (kèm field thừa nếu có)."""
    return {"tool": "refund_order", "order_id": order_id, "amount": amount,
            "currency": "VND", "reason": reason, **extra_fields}


def heading(text):
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78)


# ---------------------------------------------------------------------------
# 7. CÁC KỊCH BẢN
# ---------------------------------------------------------------------------
NOW = datetime(2026, 11, 16, 15, 0)      # thời điểm "hiện tại" của các kịch bản (15 giờ)


def scenario_same_payload_four_principals():
    heading("KỊCH BẢN 1: CÙNG MỘT payload hoàn tiền, bốn principal khác nhau")
    payload = refund()
    print("   payload:", payload)
    for title, session in [("nhân viên Mộc Trà (ops.minhanh)", "sess-minhanh"),
                           ("nhân viên Lá Xanh chỉ được XEM (ops.view_lx)", "sess-view"),
                           ("nhân viên Lá Xanh hoàn tới 500k (ops.hoa)", "sess-hoa"),
                           ("nhân viên Lá Xanh hoàn tới 300k (ops.tam)", "sess-tam")]:
        print_decision(title, execution_gate(payload, session, "APR-7731", NOW))
    print("\n   >>> Payload y nguyên, validation luôn 'đạt', nhưng kết luận về QUYỀN đổi theo principal.")


def scenario_model_claims_admin():
    heading("KỊCH BẢN 2: model tự ghi 'requested_by': 'admin' vào payload")
    payload = refund(requested_by="admin", role="admin")
    print("   payload:", payload)
    print_decision("session là ops.minhanh (Mộc Trà)", execution_gate(payload, "sess-minhanh", "APR-7731", NOW))
    print("\n   >>> Principal luôn lấy từ session đã xác thực. Field model ghi bị bỏ qua, không đổi được kết luận.")


def scenario_approval_cases():
    heading("KỊCH BẢN 3: có giấy duyệt APR-7731, gate VẪN phải kiểm tra lại")
    print_decision("(a) ops.hoa hoàn 450k cho ORD-001 lúc 15:00", execution_gate(refund(), "sess-hoa", "APR-7731", NOW))
    print_decision("(b) ops.hoa dùng APR-7731 cho ORD-002", execution_gate(refund("ORD-002", 350000), "sess-hoa", "APR-7731", NOW))
    print_decision("(c) ops.hoa gửi lúc 19:00 (approval hết hạn 18:00)",
                   execution_gate(refund(), "sess-hoa", "APR-7731", datetime(2026, 11, 16, 19, 0)))
    print_decision("(d) ops.minhanh (Mộc Trà) cầm đúng APR-7731", execution_gate(refund(), "sess-minhanh", "APR-7731", NOW))
    print_decision("(e) ops.hoa hoàn 450k nhưng KHÔNG có approval", execution_gate(refund(), "sess-hoa", None, NOW))
    print_decision("(f) ops.hoa hoàn 50k, đơn giao trễ (policy không cần duyệt)",
                   execution_gate(refund(amount=50000, reason="late_delivery"), "sess-hoa", None, NOW))


def scenario_service_account():
    heading("KỊCH BẢN 4: principal không phải người đang chat (service account đối soát)")
    print_decision("job đối soát hoàn phần tiền TRÙNG (duplicate_charge)",
                   execution_gate(refund(amount=100000, reason="duplicate_charge"), "sess-reconcile", None, NOW))
    print_decision("cùng job nhưng hoàn vì hàng vỡ (ngoài scope được giao)",
                   execution_gate(refund(amount=100000, reason="damaged_item"), "sess-reconcile", None, NOW))


def scenario_gate_placement():
    heading("KỊCH BẢN 5: đặt gate SAI chỗ (sau dispatch) và ĐÚNG chỗ (trước dispatch)")
    payload = refund()
    EFFECT_LOG.clear()
    decision = run_gate_after_dispatch(payload, "sess-minhanh", "APR-7731", NOW)
    print_decision("gate SAU dispatch: kết luận vẫn đúng ('từ chối')", decision, dispatched_before=True)
    print("      side effect đã xảy ra:", EFFECT_LOG, " <- tiền đã đi rồi (mất bò mới lo làm chuồng)")

    EFFECT_LOG.clear()
    decision = run_through_gate(payload, "sess-minhanh", "APR-7731", NOW)
    print_decision("gate TRƯỚC dispatch", decision)
    print("      side effect đã xảy ra:", EFFECT_LOG, " <- không có gì xảy ra")

    EFFECT_LOG.clear()
    run_through_gate(payload, "sess-hoa", "APR-7731", NOW)
    print("\n      (đối chiếu) cùng payload với ops.hoa, đủ căn cứ -> effect:", EFFECT_LOG)


def scenario_marketing_sms():
    heading("KỊCH BẢN 6: tin nhắn marketing, 'ưu tiên SMS' không phải căn cứ cho phép")
    for customer_id, label in [("cus-01", "khách CHỈ có 'ưu tiên SMS', chưa consent marketing"),
                               ("cus-02", "khách đã đồng ý nhận marketing")]:
        sms = {"tool": "send_marketing_sms", "customer_id": customer_id,
               "phone": "0901234567", "message": "Khuyến mãi cuối tuần tại Lá Xanh!"}
        print_decision(label, execution_gate(sms, "sess-marketing", None, NOW))


def scenario_fail_closed():
    heading("KỊCH BẢN 7: FAIL CLOSED, thiếu căn cứ bắt buộc thì không dispatch")
    print_decision("session không tồn tại (không xác định được principal)",
                   execution_gate(refund(), "sess-khong-ton-tai", "APR-7731", NOW))
    print_decision("tool lạ, không có trong danh sách", execution_gate({"tool": "delete_all_orders"}, "sess-hoa", None, NOW))
    print_decision("payload thiếu field 'reason'",
                   execution_gate({"tool": "refund_order", "order_id": "ORD-001", "amount": 1000, "currency": "VND"},
                                  "sess-hoa", None, NOW))


# ---------------------------------------------------------------------------
# 8. MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # INPUT 1 - selected: số kịch bản muốn chạy ("1".."7"); không gõ gì thì chạy cả 7.
    selected = sys.argv[1] if len(sys.argv) > 1 else "all"

    # INPUT 2 - scenarios: bảng "số kịch bản -> hàm chạy". Hàm cũng là giá trị nên bỏ vào dict được.
    scenarios = {"1": scenario_same_payload_four_principals, "2": scenario_model_claims_admin,
                 "3": scenario_approval_cases, "4": scenario_service_account,
                 "5": scenario_gate_placement, "6": scenario_marketing_sms, "7": scenario_fail_closed}

    # INPUT 3 - NOW (khai báo ở trên): thời điểm "hiện tại" giả lập, dùng để kiểm tra approval còn hạn không.
    #   Đổi giờ ở NOW (ví dụ 19:00) rồi chạy kịch bản 3 để xem approval hết hạn.
    # INPUT 4 - SESSIONS / GRANTS / APPROVALS (khai báo ở trên): "bản đồ" ai là ai, được làm gì, đã được duyệt gì.
    #   Sửa các bảng này để thử: cấp thêm quyền, đổi giới hạn, thêm approval mới.
    for key, scenario in scenarios.items():
        if selected in ("all", key):
            scenario()