"""
Bài 14: Có guardrails rồi, action đã thật sự bị chặn chưa?
Phân biệt 3 việc: CHECK (nhận xét) - GATE (chặn thật) - HITL (người quyết định, rồi quay về gate).
Không cần API key: check/gate là logic của Harness. (Check có thể là LLM-as-judge, xem NOTES_14.md)

Chạy:  python exp14_check_gate_hitl.py          (tất cả kịch bản)
       python exp14_check_gate_hitl.py 3        (chỉ kịch bản 3)
"""
import hashlib
import sys
from dataclasses import dataclass, field

# ----------------------------------------------------------------------
# 1. DỮ LIỆU: đề xuất của agent (CHƯA phải action) và verdict của check
# ----------------------------------------------------------------------
REVIEW_THRESHOLD = 200_000      # bồi thường > mức này thì cần người xem
HARD_LIMIT = 500_000            # bồi thường > mức này thì cấm hẳn
FORBIDDEN_PHRASES = ["chúng tôi thừa nhận hoàn toàn", "khởi kiện"]


@dataclass
class Proposal:
    proposal_id: str
    to: str
    body: str
    compensation: int
    parent_id: str = ""         # nếu là bản người duyệt sửa: trỏ về bản gốc

    def fingerprint(self):
        # "dấu vân tay" của NỘI DUNG: đổi chữ nào là đổi dấu vân tay
        raw = f"{self.to}|{self.body}|{self.compensation}"
        return hashlib.sha256(raw.encode()).hexdigest()[:10]


@dataclass
class Verdict:
    level: str                  # "pass" | "review" | "fail"
    reasons: list = field(default_factory=list)


@dataclass
class GateDecision:
    action: str                 # "allow" | "deny" | "escalate"
    reason: str


# ----------------------------------------------------------------------
# 2. CHECK: chỉ NHẬN XÉT, không giữ action lại
# ----------------------------------------------------------------------
def check_email(proposal):
    reasons = []
    text = proposal.body.lower()
    if proposal.compensation > HARD_LIMIT:
        return Verdict("fail", [f"bồi thường {proposal.compensation:,}đ vượt trần {HARD_LIMIT:,}đ"])
    for phrase in FORBIDDEN_PHRASES:
        if phrase in text:
            return Verdict("fail", [f"chứa cụm cấm: '{phrase}'"])
    if proposal.compensation > REVIEW_THRESHOLD:
        reasons.append(f"bồi thường {proposal.compensation:,}đ > {REVIEW_THRESHOLD:,}đ, cần người xem")
        return Verdict("review", reasons)
    return Verdict("pass", [])


# ----------------------------------------------------------------------
# 3. EXECUTOR: phần THẬT SỰ gửi email (chặng đầu tiên có effect)
# ----------------------------------------------------------------------
SENT_LOG = []       # những email đã rời khỏi hệ thống
CHECK_LOG = []      # nơi check ghi verdict


def send_email(proposal):
    SENT_LOG.append(f"{proposal.proposal_id} -> {proposal.to} (bồi thường {proposal.compensation:,}đ)")


def reset():
    SENT_LOG.clear()
    CHECK_LOG.clear()


# ----------------------------------------------------------------------
# 4. GATE: nằm TRÊN đường tới executor, đọc verdict, có quyền nói "chưa"
# ----------------------------------------------------------------------
def gate(proposal, verdict, approvals):
    """approvals: dict proposal_id -> fingerprint của bản đã được người duyệt."""
    if verdict is None:                       # không có tín hiệu = fail closed
        return GateDecision("deny", "không có verdict, từ chối (fail closed)")
    if verdict.level == "fail":
        return GateDecision("deny", "; ".join(verdict.reasons))
    if verdict.level == "pass":
        return GateDecision("allow", "check đạt")
    # verdict.level == "review": cần có phê duyệt ĐÚNG nội dung hiện tại
    approved_fp = approvals.get(proposal.proposal_id)
    if approved_fp is None:
        return GateDecision("escalate", "cần người duyệt: " + "; ".join(verdict.reasons))
    if approved_fp != proposal.fingerprint():
        return GateDecision("escalate", "nội dung đã khác bản được duyệt, phải duyệt lại")
    return GateDecision("allow", "đã được duyệt đúng nội dung này")


def run_through_gate(proposal, approvals, label=""):
    """Đường ĐÚNG: check -> gate -> (chỉ khi allow) executor."""
    verdict = check_email(proposal)
    CHECK_LOG.append(f"{proposal.proposal_id}: {verdict.level.upper()} {verdict.reasons}")
    decision = gate(proposal, verdict, approvals)
    print(f"  {label}[{proposal.proposal_id}] check={verdict.level:<6} -> gate={decision.action:<8} ({decision.reason})")
    if decision.action == "allow":
        send_email(proposal)
    return decision


# ----------------------------------------------------------------------
# 5. HITL: người duyệt quyết định, rồi quyết định QUAY VỀ GATE
# ----------------------------------------------------------------------
def handle_review(proposal, reviewer_decision, approvals):
    """reviewer_decision: ("approve",) | ("reject",) | ("edit", new_body, new_compensation)"""
    kind = reviewer_decision[0]
    if kind == "reject":
        print(f"  người duyệt TỪ CHỐI [{proposal.proposal_id}] -> không gửi")
        return None
    if kind == "approve":
        approvals[proposal.proposal_id] = proposal.fingerprint()
        print(f"  người duyệt ĐỒNG Ý [{proposal.proposal_id}] -> quay về gate")
        return run_through_gate(proposal, approvals, "(sau duyệt) ")
    if kind == "edit":
        _, new_body, new_comp = reviewer_decision
        # BẢN SỬA = ĐỀ XUẤT MỚI: id mới, check lại, gate lại. KHÔNG đi thẳng executor.
        edited = Proposal(proposal.proposal_id + "-v2", proposal.to, new_body, new_comp,
                          parent_id=proposal.proposal_id)
        print(f"  người duyệt SỬA [{proposal.proposal_id}] -> tạo đề xuất mới [{edited.proposal_id}]")
        return run_through_gate(edited, approvals, "(bản sửa) ")


# ----------------------------------------------------------------------
# 6. ĐỌC BẰNG CHỨNG: đã THẬT SỰ bị chặn chưa?
# ----------------------------------------------------------------------
def conclude(evidence):
    """evidence: dict các dấu vết mình đang có. None = không có dấu vết."""
    gate_action = evidence.get("gate")
    dispatched = evidence.get("dispatched")
    if dispatched is True:
        return "action ĐÃ chạy (executor đã nhận)."
    if gate_action is None:
        return "CHƯA BIẾT: không có bằng chứng về gate nào đọc verdict (badge/log chưa chứng minh gì)."
    if gate_action in ("deny", "escalate") and dispatched is False:
        return "ĐÃ bị chặn: có quyết định của gate VÀ xác nhận executor không chạy."
    if gate_action in ("deny", "escalate"):
        return "gate nói chặn, nhưng CHƯA có bằng chứng executor không chạy."
    return "gate cho đi, action sẽ chạy."


# ----------------------------------------------------------------------
# 7. CÁC KỊCH BẢN
# ----------------------------------------------------------------------
def make_late_delivery_email(proposal_id="E-100", compensation=250_000):
    return Proposal(proposal_id, "khach.a@example.com",
                    "Xin lỗi anh/chị vì đơn giao trễ. Chúng tôi xin bồi thường để bù đắp.",
                    compensation)


def scenario_1_check_without_gate():
    print("\n=== 1. CÓ check, KHÔNG có gate: verdict đúng, email vẫn đi ===")
    reset()
    email = make_late_delivery_email()
    verdict = check_email(email)
    CHECK_LOG.append(f"{email.proposal_id}: {verdict.level.upper()} {verdict.reasons}")
    send_email(email)                       # không có gì đứng chắn!
    print("  log của check :", CHECK_LOG)
    print("  email đã gửi  :", SENT_LOG)
    print("  => check làm đúng (REVIEW), nhưng đường gửi vẫn mở: tấm biển bên lề, không phải thanh chắn")


def scenario_2_gate_in_place():
    print("\n=== 2. CÓ gate trước executor: cùng email, cùng verdict ===")
    reset()
    approvals = {}
    email = make_late_delivery_email()
    print(" -- lần 1: chưa ai duyệt")
    run_through_gate(email, approvals)
    print("  email đã gửi:", SENT_LOG)
    print(" -- lần 2: người duyệt đồng ý, quyết định quay về gate")
    handle_review(email, ("approve",), approvals)
    print("  email đã gửi:", SENT_LOG)
    print(" -- thêm: email có cụm cấm -> gate DENY, không cần hỏi người")
    bad = Proposal("E-101", "khach.b@example.com", "Chúng tôi thừa nhận hoàn toàn lỗi của mình.", 0)
    run_through_gate(bad, approvals)
    print("  email đã gửi:", SENT_LOG)


def scenario_3_edit_is_new_proposal():
    print("\n=== 3. Người duyệt SỬA email: bản sửa phải quay về gate ===")
    # 3a. SAI: coi bản sửa là 'bản đã duyệt', gửi thẳng executor (cửa sau)
    print(" -- 3a. SAI: gửi thẳng bản sửa (người duyệt gõ nhầm thêm một số 0: 2,500,000đ)")
    reset()
    original = make_late_delivery_email("E-200", 250_000)
    typo_version = Proposal("E-200-v2", original.to, original.body, 2_500_000, parent_id="E-200")
    send_email(typo_version)
    print("  email đã gửi:", SENT_LOG)
    # 3b. ĐÚNG: bản sửa = đề xuất mới -> check lại -> gate lại
    print(" -- 3b. ĐÚNG: bản sửa đi lại check + gate")
    reset()
    approvals = {}
    handle_review(original, ("edit", original.body, 2_500_000), approvals)
    print("  email đã gửi:", SENT_LOG)
    print(" -- 3c. Người duyệt sửa hợp lý (giảm xuống 150,000đ): check đạt -> gate cho đi")
    reset()
    handle_review(original, ("edit", original.body, 150_000), approvals)
    print("  email đã gửi:", SENT_LOG)
    # 3d. Giấy duyệt cũ không dùng được cho nội dung khác
    print(" -- 3d. Giấy duyệt gắn với NỘI DUNG: đổi nội dung nhưng giữ nguyên id thì gate vẫn bắt")
    reset()
    approvals = {"E-300": make_late_delivery_email("E-300", 250_000).fingerprint()}
    tampered = make_late_delivery_email("E-300", 480_000)
    run_through_gate(tampered, approvals)
    print("  email đã gửi:", SENT_LOG)


def scenario_4_hitl_cost():
    print("\n=== 4. Cái giá của HITL: mọi email đều chờ người duyệt ===")

    # 100 email: 90 email cảm ơn, 8 email bồi thường ổn, 2 email bồi thường CÓ VẤN ĐỀ ẨN
    emails = []
    for i in range(1, 101):
        if i in (93, 97):
            emails.append((Proposal(f"M-{i}", "x@example.com", "bồi thường", 300_000), True))
        elif i % 12 == 0 and i < 90:
            emails.append((Proposal(f"M-{i}", "x@example.com", "bồi thường", 250_000), False))
        else:
            emails.append((Proposal(f"M-{i}", "x@example.com", "cảm ơn quý khách", 0), False))

    def tired_reviewer(has_problem, approve_streak):
        # Người đã bấm đồng ý liên tục >= 10 lần thì bấm theo quán tính (approval fatigue)
        if approve_streak >= 10:
            return "approve"
        return "reject" if has_problem else "approve"

    def simulate(route_everything):
        queue_size = 0
        streak = 0
        slipped = 0
        for proposal, has_problem in emails:
            level = check_email(proposal).level
            needs_human = True if route_everything else (level == "review")
            if not needs_human:
                continue
            queue_size += 1
            decision = tired_reviewer(has_problem, streak)
            if decision == "approve":
                streak += 1
                if has_problem:
                    slipped += 1
            else:
                streak = 0
        return queue_size, slipped

    q_all, slip_all = simulate(route_everything=True)
    q_risk, slip_risk = simulate(route_everything=False)
    print(f"  Mọi email qua người : hàng đợi {q_all:>3} email, email có vấn đề lọt qua: {slip_all}")
    print(f"  Chỉ email rủi ro    : hàng đợi {q_risk:>3} email, email có vấn đề lọt qua: {slip_risk}")
    print("  => duyệt NHIỀU hơn không có nghĩa là AN TOÀN hơn")


def scenario_5_read_evidence():
    print("\n=== 5. Đọc bằng chứng: 'có guardrails' đã đủ chưa? ===")
    cases = [
        ("Giao diện hiện badge 'safe'",                      {"gate": None, "dispatched": None}),
        ("Log có dòng REVIEW, không thấy gate nào",          {"gate": None, "dispatched": None}),
        ("Gate ghi DENY, chưa biết executor có chạy không",  {"gate": "deny", "dispatched": None}),
        ("Gate ghi DENY và executor xác nhận KHÔNG chạy",    {"gate": "deny", "dispatched": False}),
        ("Log REVIEW nhưng executor đã gửi email",           {"gate": None, "dispatched": True}),
    ]
    for title, evidence in cases:
        print(f"  - {title}\n      => {conclude(evidence)}")


SCENARIOS = {
    1: scenario_1_check_without_gate,
    2: scenario_2_gate_in_place,
    3: scenario_3_edit_is_new_proposal,
    4: scenario_4_hitl_cost,
    5: scenario_5_read_evidence,
}


def main():
    # Đầu vào duy nhất: số kịch bản muốn chạy. Bỏ trống = chạy cả 5.
    #   1 = check không có gate   2 = gate đứng đúng chỗ   3 = người duyệt sửa nội dung
    #   4 = chi phí HITL          5 = đọc bằng chứng
    if len(sys.argv) > 1:
        SCENARIOS[int(sys.argv[1])]()
    else:
        for run in SCENARIOS.values():
            run()


if __name__ == "__main__":
    main()