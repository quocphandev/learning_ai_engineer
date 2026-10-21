import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
client = genai.Client()
MODEL = "gemini-3.5-flash-lite"  # đổi nếu AI Studio có bản flash mới hơn

# --- 1. Tool giả ---
ORDERS = {
    "4821": {"status": "đã giao", "total": 350000},
    "5000": {"status": "kẹt ở kho", "total": 120000},
}


def lookup_order(order_id: str) -> dict:
    return ORDERS.get(order_id, {"error": "không tìm thấy đơn"})


def create_refund(order_id: str) -> dict:
    return {"ok": True, "refund_for": order_id}


TOOLS = {"lookup_order": lookup_order, "create_refund": create_refund}
ALLOWED = set(TOOLS) | {"done"}

# --- 2. Quy ước để model "đề xuất" ---
SYSTEM = """Bạn là trợ lý hỗ trợ khách hàng của một cửa hàng online.
Mỗi lượt, CHỈ trả về MỘT JSON duy nhất, không thêm chữ nào khác.
Các dạng JSON hợp lệ:
{"action": "lookup_order", "args": {"order_id": "<mã đơn>"}}   -> tra cứu đơn hàng
{"action": "create_refund", "args": {"order_id": "<mã đơn>"}}  -> tạo yêu cầu hoàn tiền
{"action": "done", "message": "<lời trả lời cho khách>"}       -> kết thúc và trả lời khách
Hãy tự quyết định bước tiếp theo dựa trên yêu cầu của khách và kết quả các bước trước đó.
Khi đã đủ thông tin để trả lời khách hoặc cần hỏi lại khách, dùng action "done"."""


# --- 3. Gọi model ---
def llm(contents) -> str:
    response = client.models.generate_content(
        model=MODEL,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            response_mime_type="application/json",
        ),
    )
    return response.text


# --- 4. Trạm kiểm soát ---
def parse(text: str):
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def validate(proposal, looked_up):
    if proposal is None:
        return "Output không phải JSON hợp lệ"
    action = proposal.get("action")
    if action not in ALLOWED:
        return f"Action '{action}' không nằm trong tập được phép"
    if action in TOOLS:
        args = proposal.get("args")
        if not isinstance(args, dict) or "order_id" not in args:
            return "Thiếu args.order_id"
        if action == "create_refund" and args["order_id"] not in looked_up:
            return "Phải tra cứu đơn (lookup_order) trước khi hoàn tiền"
    return None


# --- 5. Vòng lặp ---
def run_agent(user_message: str, max_steps: int = 6):
    contents = [{"role": "user", "parts": [{"text": user_message}]}]
    looked_up, trace = set(), []

    for _ in range(max_steps):
        text = llm(contents)  # model đề xuất
        proposal = parse(text)
        contents.append({"role": "model", "parts": [{"text": text}]})

        error = validate(proposal, looked_up)  # trạm kiểm soát
        if error:
            trace.append(f"[BỊ CHẶN] {error}")
            contents.append({"role": "user", "parts": [{"text": f"Bị từ chối: {error}"}]})
            continue

        action = proposal["action"]
        if action == "done":
            trace.append(f"done -> {proposal.get('message')}")
            return trace

        args = proposal["args"]
        result = TOOLS[action](order_id=args["order_id"])  # chỉ chạy khi hợp lệ
        if action == "lookup_order":
            looked_up.add(args["order_id"])
        trace.append(f"{action}({args}) -> {result}")
        contents.append({
            "role": "user",
            "parts": [{"text": "Kết quả: " + json.dumps(result, ensure_ascii=False)}],
        })

    trace.append("[DỪNG] quá số bước tối đa")
    return trace


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Tôi muốn hoàn tiền đơn 4821"
    print("Khách:", q)
    for i, step in enumerate(run_agent(q), 1):
        print(f"  Bước {i}: {step}")