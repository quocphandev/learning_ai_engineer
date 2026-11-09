"""Bài 11 - Hallucination: model trả lời rất chắc chắn, nhưng dựa vào đâu?

Ba trục độc lập:  confidence (giọng điệu)  |  grounding (căn cứ)  |  informational truth (đúng sự thật)
Ba câu hỏi trước khi tin một nguồn:  relevance  |  freshness  |  authority

Cách chạy:
    python exp11_grounding_check.py fake          # chấm cả 6 câu trả lời A-F, KHÔNG cần API key
    python exp11_grounding_check.py fake A        # chỉ chấm câu trả lời A
    python exp11_grounding_check.py real          # dùng Gemini làm "thẩm phán" relevance (cần llm.py + .env)
"""
import json
import sys
from dataclasses import dataclass
from datetime import date


# ---------------------------------------------------------------------------
# 1. DỮ LIỆU: các tài liệu nguồn (kèm metadata) và 6 câu trả lời cần chấm
# ---------------------------------------------------------------------------
POLICY_OWNER = "Tiệm giày Gót Nhẹ"      # bên CÓ THẨM QUYỀN ban hành chính sách đổi trả
ASKED_ON = date(2026, 11, 2)            # thời điểm khách đặt câu hỏi (dùng để kiểm tra freshness)

DOCUMENTS = {
    # Bản chính sách ĐANG có hiệu lực. "facts" là điều mỗi Mục khẳng định (để máy so khớp ở chế độ fake).
    "policy_0701": {
        "title": "Chính sách đổi trả (áp dụng từ 01/07)",
        "issuer": POLICY_OWNER,
        "effective_from": date(2026, 7, 1),
        "superseded_on": None,
        "reachable": True,
        "sections": {
            1: {"text": "Khách hàng được đổi sang size hoặc mẫu khác trong vòng 7 ngày kể từ ngày nhận hàng, "
                        "với điều kiện sản phẩm chưa qua sử dụng, còn nguyên tem và hộp.",
                "facts": {"exchange_window_days": 7, "exchange_requires_unused": True}},
            2: {"text": "Hoàn tiền chỉ áp dụng cho sản phẩm lỗi do sản xuất, trong vòng 7 ngày kể từ ngày nhận hàng.",
                "facts": {"refund_window_days": 7, "refund_for_non_defective_items": False}},
            3: {"text": "Sản phẩm mua trong chương trình giảm giá chỉ được đổi size, không đổi sang mẫu khác.",
                "facts": {"sale_items_exchange_size_only": True}},
        },
    },
    # Bản CŨ: đã bị thay bằng bản 01/07 (freshness)
    "policy_0101": {
        "title": "Chính sách đổi trả (áp dụng từ 01/01)",
        "issuer": POLICY_OWNER,
        "effective_from": date(2026, 1, 1),
        "superseded_on": date(2026, 7, 1),
        "reachable": True,
        "sections": {
            1: {"text": "Khách hàng được trả hàng và hoàn tiền trong vòng 30 ngày kể từ ngày nhận, không cần nêu lý do.",
                "facts": {"refund_window_days": 30, "refund_for_non_defective_items": True}},
        },
    },
    # Bài blog: nội dung có thật nhưng KHÔNG phải bên ban hành chính sách (authority)
    "blog_review": {
        "title": "Kinh nghiệm săn sale giày cuối năm (blog review)",
        "issuer": "Blog Săn Sale Giày",
        "effective_from": date(2026, 3, 15),
        "superseded_on": None,
        "reachable": True,
        "sections": {
            1: {"text": "Hàng giảm giá ở Gót Nhẹ vẫn hoàn tiền bình thường nha.",
                "facts": {"refund_for_non_defective_items": True}},
        },
    },
    # Link không mở được (trang lỗi)
    "policy_page_404": {
        "title": "Chính sách đổi trả (trang lỗi 404)",
        "issuer": POLICY_OWNER,
        "effective_from": date(2026, 7, 1),
        "superseded_on": None,
        "reachable": False,
        "sections": {},
    },
}


def claim(text, topic, value, cite_doc=None, cite_section=None):
    """Tạo một claim: câu khẳng định + 'topic/value' (để máy so khớp) + nguồn được dẫn."""
    return {"text": text, "topic": topic, "value": value, "cite_doc": cite_doc, "cite_section": cite_section}


# Mỗi câu trả lời đã được TÁCH thành các claim (từng mảnh khẳng định riêng).
# "truth" là nhãn đúng/sai thật, chỉ để so sánh. Ngoài đời bạn KHÔNG có sẵn nhãn này.
ANSWERS = {
    "A": {
        "text": "Chắc chắn được bạn nhé! Theo chính sách của cửa hàng, bạn có 7 ngày kể từ ngày nhận hàng "
                "để gửi trả sản phẩm chưa qua sử dụng và nhận lại tiền. Nguồn: Chính sách đổi trả",
        "claims": [
            claim("Có 7 ngày kể từ ngày nhận hàng", "refund_window_days", 7, "policy_0701"),
            claim("Sản phẩm phải chưa qua sử dụng", "exchange_requires_unused", True, "policy_0701"),
            claim("Gửi trả giày chật vẫn được nhận lại tiền", "refund_for_non_defective_items", True, "policy_0701"),
        ],
        "truth": False,
    },
    "B": {
        "text": "Chắc chắn nhé, bạn được trả hàng và hoàn tiền trong vòng 30 ngày kể từ ngày nhận, "
                "không cần nêu lý do. Nguồn: Chính sách đổi trả (áp dụng từ 01/01)",
        "claims": [
            claim("Được hoàn tiền trong 30 ngày", "refund_window_days", 30, "policy_0101"),
            claim("Hoàn tiền cả khi hàng không lỗi", "refund_for_non_defective_items", True, "policy_0101"),
        ],
        "truth": False,
    },
    "C": {
        "text": "Chắc chắn luôn, hàng giảm giá ở Gót Nhẹ vẫn hoàn tiền bình thường nha. "
                "Nguồn: Kinh nghiệm săn sale giày cuối năm (blog review)",
        "claims": [
            claim("Hàng giảm giá vẫn được hoàn tiền", "refund_for_non_defective_items", True, "blog_review"),
        ],
        "truth": False,
    },
    "D": {
        "text": "Chắc chắn: hàng giảm giá thì chỉ đổi size trong 7 ngày thôi bạn, không hoàn tiền nếu sản phẩm không lỗi.",
        "claims": [
            claim("Hàng giảm giá chỉ được đổi size", "sale_items_exchange_size_only", True),
            claim("Không hoàn tiền nếu sản phẩm không lỗi", "refund_for_non_defective_items", False),
        ],
        "truth": True,
    },
    "E": {
        "text": "Mình không chắc hoàn toàn về trường hợp của bạn, nhưng theo Mục 2 trong chính sách, hoàn tiền chỉ áp dụng "
                "cho sản phẩm lỗi do sản xuất. Với giày bị chật, Mục 1 và Mục 3 cho phép đổi sang size khác trong 7 ngày. "
                "Nguồn: Chính sách đổi trả",
        "claims": [
            claim("Hoàn tiền chỉ áp dụng cho hàng lỗi", "refund_for_non_defective_items", False, "policy_0701", 2),
            claim("Được đổi trong 7 ngày", "exchange_window_days", 7, "policy_0701", 1),
            claim("Hàng giảm giá chỉ đổi size", "sale_items_exchange_size_only", True, "policy_0701", 3),
        ],
        "truth": True,
    },
    "F": {
        "text": "Chắc chắn, theo chính sách đổi trả mới nhất thì hoàn tiền chỉ áp dụng cho hàng lỗi. "
                "Nguồn: Chính sách đổi trả (link)",
        "claims": [
            claim("Hoàn tiền chỉ áp dụng cho hàng lỗi", "refund_for_non_defective_items", False, "policy_page_404"),
        ],
        "truth": True,
    },
}


# ---------------------------------------------------------------------------
# 2. TRỤC 1 - CONFIDENCE: chỉ đọc GIỌNG ĐIỆU của câu chữ (không liên quan độ tin cậy)
# ---------------------------------------------------------------------------
CONFIDENT_MARKERS = ["chắc chắn", "theo quy định", "đảm bảo", "100%"]
HEDGE_MARKERS = ["không chắc", "chưa chắc", "mình nghĩ"]


def detect_tone(text):
    lowered = text.lower()
    if any(marker in lowered for marker in HEDGE_MARKERS):
        return "dè dặt"
    if any(marker in lowered for marker in CONFIDENT_MARKERS):
        return "rất chắc chắn"
    return "trung tính"


# ---------------------------------------------------------------------------
# 3. TRỤC 2 - GROUNDING: từng claim có bám vào một đoạn nguồn cụ thể không?
#    "Relevance" = đoạn đó có THẬT SỰ nói điều claim khẳng định không?
# ---------------------------------------------------------------------------
def select_sections(claim_item, document):
    """Chỉ xét Mục mà claim dẫn tới; nếu không nêu Mục thì xét mọi Mục của tài liệu."""
    sections = document["sections"]
    wanted = claim_item["cite_section"]
    if wanted is None:
        return sections
    return {wanted: sections[wanted]} if wanted in sections else {}


def judge_relevance_rule(claim_item, document):
    """Thẩm phán dùng luật (chế độ fake): so 'topic/value' của claim với 'facts' của từng Mục.
    Trả về (status, số Mục). status: supported | contradicted | not_found."""
    for number, section in select_sections(claim_item, document).items():
        facts = section["facts"]
        if claim_item["topic"] in facts:
            if facts[claim_item["topic"]] == claim_item["value"]:
                return "supported", number
            return "contradicted", number
    return "not_found", None


JUDGE_PROMPT = """Bạn là thẩm phán kiểm tra căn cứ. Cho một CLAIM và các Mục của một tài liệu.
Chỉ dựa vào chữ trong tài liệu, không dùng kiến thức bên ngoài. Trả về MỘT JSON:
{"status": "supported" | "contradicted" | "not_found", "section": <số Mục hoặc null>}
- supported: có Mục nói đúng điều claim khẳng định
- contradicted: có Mục nói điều NGƯỢC với claim
- not_found: không Mục nào nói về điều claim khẳng định"""


def judge_relevance_gemini(claim_item, document, chat=None):
    """Thẩm phán là Gemini (chế độ real). Lưu ý: bản thân thẩm phán LLM cũng có thể sai."""
    if chat is None:
        import common.llm as llm_module  # llm.py bạn đã làm ở bài 03
        chat = llm_module.call_llm
    sections = select_sections(claim_item, document)
    sections_text = "\n".join(f"Mục {number}: {section['text']}" for number, section in sections.items())
    raw = chat(JUDGE_PROMPT, f"CLAIM: {claim_item['text']}\n\nTÀI LIỆU:\n{sections_text}", json_mode=True)
    try:
        data = json.loads(raw)
        status = data.get("status")
        section = int(data["section"]) if data.get("section") is not None else None
    except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
        return "not_found", None        # thẩm phán trả sai định dạng: coi như không tìm thấy căn cứ
    if status not in ("supported", "contradicted"):
        return "not_found", None
    return status, section


# ---------------------------------------------------------------------------
# 4. FRESHNESS và AUTHORITY: hai câu hỏi thêm cho một nguồn ĐÃ khớp nội dung
# ---------------------------------------------------------------------------
def check_freshness(document, asked_on):
    """Đây có phải bản đang có hiệu lực TẠI THỜI ĐIỂM hỏi không?"""
    if document["effective_from"] > asked_on:
        return False, "bản này chưa có hiệu lực"
    superseded_on = document["superseded_on"]
    if superseded_on is not None and superseded_on <= asked_on:
        return False, f"bản này đã bị thay thế từ {superseded_on:%d/%m/%Y}"
    return True, f"đang hiệu lực (từ {document['effective_from']:%d/%m/%Y})"


def check_authority(document):
    """Nơi phát hành có thẩm quyền quyết định chuyện này không?"""
    if document["issuer"] != POLICY_OWNER:
        return False, f"nguồn do '{document['issuer']}' phát hành, không phải bên ban hành chính sách"
    return True, f"do chính '{POLICY_OWNER}' ban hành"


# ---------------------------------------------------------------------------
# 5. CHẤM TỪNG CLAIM, RỒI CẢ CÂU TRẢ LỜI
# ---------------------------------------------------------------------------
@dataclass
class ClaimResult:
    text: str
    verdict: str        # VERIFIED | UNVERIFIABLE | UNSUPPORTED | STALE | LOW_AUTHORITY
    reason: str
    grounded: bool      # đoạn nguồn có thật sự nói điều claim khẳng định không
    passage: str = ""   # đoạn nguồn đã dùng để đối chiếu


def verify_claim(claim_item, asked_on, judge):
    """Đưa một claim qua: có nguồn? mở được? khớp nội dung? còn hiệu lực? đúng thẩm quyền?"""
    text = claim_item["text"]
    doc_id = claim_item["cite_doc"]

    if doc_id is None:
        return ClaimResult(text, "UNVERIFIABLE", "không kèm nguồn: không có gì để mở ra đối chiếu", False)
    document = DOCUMENTS.get(doc_id)
    if document is None or not document["reachable"]:
        return ClaimResult(text, "UNVERIFIABLE", "link không mở được: chưa có căn cứ nói đúng hay sai", False)

    status, section_number = judge(claim_item, document)
    if status != "not_found" and section_number not in document["sections"]:
        status = "not_found"            # thẩm phán chỉ tới Mục không tồn tại -> không tin
    if status == "not_found":
        return ClaimResult(text, "UNSUPPORTED", f"không đoạn nào trong \"{document['title']}\" nói điều này", False)

    passage = document["sections"][section_number]["text"]
    if status == "contradicted":
        return ClaimResult(text, "UNSUPPORTED", f"Mục {section_number} nói điều NGƯỢC LẠI", False, passage)

    fresh_ok, fresh_detail = check_freshness(document, asked_on)
    auth_ok, auth_detail = check_authority(document)
    detail = f"Mục {section_number} | {fresh_detail} | {auth_detail}"
    if not fresh_ok:
        return ClaimResult(text, "STALE", detail, True, passage)
    if not auth_ok:
        return ClaimResult(text, "LOW_AUTHORITY", detail, True, passage)
    return ClaimResult(text, "VERIFIED", detail, True, passage)


PROBLEM_VERDICTS = {"UNSUPPORTED", "STALE", "LOW_AUTHORITY"}


def overall_decision(results):
    """Kết luận cho cả câu trả lời: chỉ 'đã kiểm chứng' khi MỌI claim đều VERIFIED."""
    verdicts = {result.verdict for result in results}
    if verdicts == {"VERIFIED"}:
        return "ĐÃ KIỂM CHỨNG: có căn cứ để quyết định"
    if verdicts & PROBLEM_VERDICTS:
        return "CÓ VẤN ĐỀ: đừng dựa vào câu trả lời này"
    return "CHƯA KIỂM CHỨNG ĐƯỢC: cần thêm bằng chứng trước khi quyết định"


# ---------------------------------------------------------------------------
# 6. IN KẾT QUẢ
# ---------------------------------------------------------------------------
def print_answer_report(answer_id, answer, results):
    print("\n" + "=" * 76 + f"\nCÂU TRẢ LỜI {answer_id}\n" + "=" * 76)
    print(f"   Nội dung : {answer['text']}")
    print(f"   Giọng điệu: {detect_tone(answer['text'])}   (chỉ cho biết cách viết, KHÔNG phải độ tin cậy)")
    print("   Từng claim:")
    for result in results:
        print(f"     [{result.verdict:<13}] {result.text}")
        print(f"        -> {result.reason}")
        if result.passage:
            print(f"        -> đoạn nguồn: \"{result.passage}\"")
    print(f"   >>> KẾT LUẬN: {overall_decision(results)}")


def print_summary_matrix(rows):
    print("\n" + "=" * 76 + "\nBẢNG TỔNG HỢP: ba trục độc lập\n" + "=" * 76)
    print(f"{'Câu':<4}{'Giọng điệu':<15}{'Bám nguồn':<14}{'Đúng thật?':<12}Kết luận của bộ kiểm tra")
    for answer_id, tone, grounded_text, truth, decision in rows:
        print(f"{answer_id:<4}{tone:<15}{grounded_text:<14}{('đúng' if truth else 'sai'):<12}{decision}")


# ---------------------------------------------------------------------------
# 7. MAIN
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # INPUT 1 - mode: lấy từ dòng lệnh (python exp11_grounding_check.py fake | real)
    #   "fake": thẩm phán relevance là luật so khớp 'topic/value', không tốn API
    #   "real": thẩm phán relevance là Gemini đọc chữ trong tài liệu
    mode = sys.argv[1] if len(sys.argv) > 1 else "fake"

    # INPUT 2 - selected: (tùy chọn) chỉ chấm một câu trả lời, ví dụ "A". Không gõ thì chấm cả A-F.
    selected = sys.argv[2].upper() if len(sys.argv) > 2 else None

    # INPUT 3 - judge: hàm làm nhiệm vụ "đoạn nguồn có nói đúng điều claim khẳng định không?"
    #   Truyền hàm vào (dependency injection) để đổi thẩm phán mà không sửa verify_claim.
    judge = judge_relevance_rule if mode == "fake" else judge_relevance_gemini

    # INPUT 4 - ASKED_ON (khai báo ở đầu file): thời điểm khách hỏi, dùng để kiểm tra bản nguồn còn hiệu lực không.
    summary_rows = []
    for answer_id, answer in ANSWERS.items():
        if selected and answer_id != selected:
            continue
        results = [verify_claim(item, ASKED_ON, judge) for item in answer["claims"]]
        print_answer_report(answer_id, answer, results)

        grounded_count = sum(1 for result in results if result.grounded)
        summary_rows.append((answer_id, detect_tone(answer["text"]),
                             f"{grounded_count}/{len(results)} claim", answer["truth"], overall_decision(results)))

    print_summary_matrix(summary_rows)