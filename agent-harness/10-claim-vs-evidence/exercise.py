# Bài 10 — Model nói "đã làm", nhưng bằng chứng đâu?
from dataclasses import dataclass


# [GÕ] ===== 1. RECORD: dấu vết do HỆ THỐNG THẬT ghi lại =====
@dataclass
class Record:
    source: str      # bên nào ghi
    kind: str        # dispatch | execution | provider_receipt | domain_record
    value: str       # trạng thái được ghi
    time: str


# [GÕ] ===== 2. CONTRACT: mỗi record xác nhận TỚI ĐÂU =====
# (source, value) -> những fact mà record này chứng minh, theo tài liệu của bên ghi
CONTRACTS = {
    ("harness", "dispatched"): {
        "confirms": {"command_dispatched"},
        "meaning": "lệnh đã rời harness", "stops_at": "bên nhận lệnh làm gì"},
    ("notification_tool", "ok"): {
        "confirms": {"tool_executed"},
        "meaning": "tool tự báo đã chạy xong", "stops_at": "provider làm gì tiếp"},
    ("email_provider", "accepted"): {
        "confirms": {"provider_accepted"},
        "meaning": "thư đã vào hàng đợi gửi", "stops_at": "thư đã tới hộp thư chưa"},
    ("email_provider", "delivered"): {
        "confirms": {"provider_accepted", "delivered_to_inbox"},
        "meaning": "thư đã tới hộp thư người nhận", "stops_at": "khách đã đọc chưa"},
    ("order_system", "customer_notified"): {
        "confirms": {"order_recorded_notified"},
        "meaning": "ghi khi provider đã tiếp nhận thư", "stops_at": "khách đã biết chưa"},
    ("calendar_service", "event_created"): {
        "confirms": {"event_on_calendar"},
        "meaning": "event tồn tại đúng giờ, đúng người", "stops_at": "khách mời đã đọc / sẽ dự chưa"},
}


# [GÕ] ===== 3. COMPLETION CONDITION: "xong" nghĩa là gì =====
@dataclass
class Requirement:
    fact: str        # fact cần được chứng minh
    owner: str       # hệ thống SỞ HỮU fact đó (bước 2)
    label: str


# [GÕ] ===== 4. BỐN BƯỚC KIỂM TRA MỘT CÂU "ĐÃ LÀM" =====
def read_scope(records: list[Record]) -> tuple[set[str], list[str]]:
    """Bước 3: đọc phạm vi từng record theo contract."""
    proven: set[str] = set()
    lines: list[str] = []
    for record in records:
        contract = CONTRACTS.get((record.source, record.value))
        if contract is None:
            lines.append(f"[{record.kind}] {record.source}={record.value}: KHÔNG có contract → không dùng làm căn cứ")
            continue
        proven |= contract["confirms"]
        lines.append(f"[{record.kind}] {record.source}={record.value}: {contract['meaning']}"
                     f" | dừng ở: {contract['stops_at']}")
    return proven, lines


def verify_claim(claim: str, condition: list[Requirement], records: list[Record],
                 records_visible: bool = True) -> tuple[str, list[str]]:
    # Bước 1: làm rõ claim + completion condition
    notes = [f"Claim của model: \"{claim}\" (lời kể, KHÔNG dùng để kết luận)",
             "Condition: " + " + ".join(req.label for req in condition)]
    # Bước 2: hệ thống nào sở hữu fact
    notes.append("Hệ thống sở hữu fact: " + ", ".join(sorted({req.owner for req in condition})))

    if not records_visible:
        notes.append("Không có quyền xem record → không xác nhận được, cũng không bác bỏ được.")
        return "CHƯA BIẾT", notes

    proven, scope_lines = read_scope(records)          # Bước 3
    notes += scope_lines

    missing = [req for req in condition if req.fact not in proven]   # Bước 4
    if not missing:
        return "ĐỦ", notes
    for req in missing:
        notes.append(f"Thiếu record có contract xác nhận: {req.label} (do {req.owner} ghi)")
    notes.append("Lưu ý: thiếu record ≠ việc chưa xảy ra. Chỉ là chưa đủ căn cứ.")
    return "CHƯA ĐỦ", notes


def guess_by_name(records: list[Record]) -> str:
    """CÁCH SAI: đoán theo tên trạng thái thay vì đọc contract."""
    if any("notified" in record.value or "accepted" in record.value for record in records):
        return "XONG (vì 'customer_notified' nghe như khách đã biết)"
    return "chưa"


# [COPY] ===== 5. DỮ LIỆU TÌNH HUỐNG =====
CLAIM_EMAIL = "Đã gửi thông báo cho khách của đơn ORD-001."
FOUR_RECORDS = [
    Record("harness", "dispatch", "dispatched", "14:02:07"),
    Record("notification_tool", "execution", "ok", "14:02:08"),
    Record("email_provider", "provider_receipt", "accepted", "14:02:08"),
    Record("order_system", "domain_record", "customer_notified", "14:02:09"),
]

COND_ACCEPTED_AND_RECORDED = [
    Requirement("provider_accepted", "email_provider", "provider đã tiếp nhận thư"),
    Requirement("order_recorded_notified", "order_system", "hệ thống đơn đã ghi nhận"),
]
COND_CUSTOMER_READ = [Requirement("customer_read", "email_provider", "khách đã đọc thư")]
COND_IN_INBOX = [Requirement("delivered_to_inbox", "email_provider", "thư đã tới hộp thư khách")]

CLAIM_CALENDAR = "Đã tạo lịch họp."
CALENDAR_RECORDS = [Record("calendar_service", "provider_receipt + domain_record", "event_created", "09:15")]
COND_EVENT = [Requirement("event_on_calendar", "calendar_service", "có event đúng giờ, đúng người")]
COND_ATTENDING = [Requirement("all_attendees_confirmed", "calendar_service", "mọi người xác nhận tham dự")]

SCENARIOS = [
    ("1. Condition: provider tiếp nhận + hệ thống đơn ghi nhận", CLAIM_EMAIL, COND_ACCEPTED_AND_RECORDED, FOUR_RECORDS, True),
    ("2. Cùng record, condition: khách ĐÃ ĐỌC", CLAIM_EMAIL, COND_CUSTOMER_READ, FOUR_RECORDS, True),
    ("3. Cùng record, condition: thư ĐÃ TỚI HỘP THƯ", CLAIM_EMAIL, COND_IN_INBOX, FOUR_RECORDS, True),
    ("4. Thêm record 'delivered' của provider", CLAIM_EMAIL, COND_IN_INBOX,
     FOUR_RECORDS + [Record("email_provider", "provider_receipt", "delivered", "14:03:30")], True),
    ("5. Chỉ thấy dispatch + execution", CLAIM_EMAIL, COND_ACCEPTED_AND_RECORDED, FOUR_RECORDS[:2], True),
    ("6. Không có quyền xem record (chỉ có khung chat)", CLAIM_EMAIL, COND_ACCEPTED_AND_RECORDED, FOUR_RECORDS, False),
    ("7. Lịch họp: condition 'có event đúng giờ, đúng người'", CLAIM_CALENDAR, COND_EVENT, CALENDAR_RECORDS, True),
    ("8. Lịch họp: condition 'mọi người xác nhận tham dự'", CLAIM_CALENDAR, COND_ATTENDING, CALENDAR_RECORDS, True),
]


# [COPY] ===== 6. CHẠY =====
def main() -> None:
    for title, claim, condition, records, visible in SCENARIOS:
        status, notes = verify_claim(claim, condition, records, visible)
        print(f"\n{title}\n   → KẾT LUẬN: {status}")
        for note in notes:
            print(f"     · {note}")
        if title.startswith("2."):
            print(f"   ⚠️  Nếu đoán theo tên: {guess_by_name(records)}")


if __name__ == "__main__":
    main()