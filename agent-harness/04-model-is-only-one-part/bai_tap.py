# Mode chỉ là một phần của hệ thống Agent
import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

# Cho phép import thư mục common/ nằm ở thư mục cha (agent-harness/)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import common.llm as llm_module  # noqa: E402

NOW = datetime(2026, 10, 21, 22, 0)
STALE_AFTER_HOURS = 48
QUESTION = "Đơn ORD-001 của tôi đang ở đâu?"

# ===== VÙNG 4: ENVIRONMENT =====
FRESH_ORDER_DB = {
    "ORD-001": {
        "status": "Đang giao",
        "location": "Bưu cục Thủ Đức",
        "updated_at": "2026-10-21 08:30"
    }
}

STALE_ORDER_DB = {
    "ORD-001": {
        "status": "Đang xử lý",
        "location": "Chưa xuất kho",
        "updated_at": "2026-10-12 09:00"
    }
}

def _lookup(db: dict, args: dict) -> dict:
    order_id = str(args.get("order_id") or args.get("id") or "").strip().upper()
    if order_id in db:
        return {"order_id": order_id, **db[order_id]}
    return {"error": f"Không tìm thấy đơn {order_id}"}


def lookup_order_fresh(args: dict) -> dict:
    return _lookup(FRESH_ORDER_DB, args)

def lookup_order_stale(args: dict) -> dict:
    return _lookup(STALE_ORDER_DB, args)

# --- Test bước 1 ---

    
# print("--- Test bước 1 ---")
# print(lookup_order_fresh({"order_id": " ORD - 001 "}))
# print(lookup_order_stale({"order_id": "ORD-001"}))
# print(lookup_order_fresh({"order_id": "ORD-222"}))

# --- Test bước 2 ---
# ===== VÙNG 2: AGENT CONFIGUARATION =====

@dataclass
class AgentConfig:
    name: str
    instructions: str
    tool_descriptions: dict[str, str] = field(default_factory=dict)


GOOD_CONFIG = AgentConfig(
    name = "mô tả tool rõ ràng",
    instructions=("Bạn là trợ lý CSKH của cửa hàng. Trả lơi ngắn gọn bằng Tiếng Việt. "
    "Khi khách hàng hỏi về một đơn hàng cụ thể, hãy dùng tool để lấy dữ liệu thật, "
    "Không đoán."
    ),
    tool_descriptions={
        "lookup_order": (
            "Tra cứu trạng thái và vị trí hiện tại của một đơn hàng. "
            "Dùng khi khách hàng hỏi đơn hàng ở đâu hoặc đã giao chưa. "
            "Tham số: order_id (ví dụ ORD-001)."
        )
    },
)

VAGUE_CONFIG = AgentConfig(
    name = "mô tả tool mơ hồ",
    instructions = "Bạn là trợ lý CSKH của cửa hàng. Trả lời ngắn gọn bằng Tiếng Việt.",
    tool_descriptions={"tool_x": "Xử lý dữ liệu nội bộ. Tham số: id."},
)

DECLARATION_ONLY_CONFIG = AgentConfig(
    name = "chỉ có capability declaration",
    instructions = (
        "Bạn là trợ lý CSKH của cửa hàng. Bạn có khả năng tra cứu đơn hàng "
        "của khách. Trả lời ngắn gọn bằng tiếng Việt."
    )
)

# --- Test 2 ---
# print(GOOD_CONFIG.name, "→", list(GOOD_CONFIG.tool_descriptions))
# print(VAGUE_CONFIG.name, "→", list(VAGUE_CONFIG.tool_descriptions))
# print(DECLARATION_ONLY_CONFIG.name, "→", list(DECLARATION_ONLY_CONFIG.tool_descriptions))
    
# ===== VÙNG 1: MODEL =====
# Mọi model đều có cùng hình dạng: (system, prompt, json_mode) -> str

def gemini_model(system: str, prompt: str, json_mode: bool) -> str:
    result = llm_module.call_llm(prompt, system=system, json_mode=json_mode, temperature=0)
    return result.text


def fake_model(system: str, prompt: str, json_mode: bool) -> str:
    """Model GIẢ bắt chước hành vi điển hình của LLM, dùng để học khi hết quota."""
    # Không có tool, nhưng được dặn "bạn có khả năng tra cứu" → kể như đã tra
    if not json_mode:
        return "Mình đã kiểm tra rồi, đơn ORD-001 của bạn đang trên đường giao, 1-2 ngày nữa tới nhé."

    lines = prompt.splitlines()
    observations = [line for line in lines if line.startswith("OBSERVATION:")]
    harness_notes = [line for line in lines if line.startswith("HARNESS:")]

    # Đã có dữ liệu thật → trả lời dựa trên dữ liệu đó
    if observations:
        data = json.loads(observations[-1][len("OBSERVATION:"):])
        if "error" in data:
            text = f"Xin lỗi, mình chưa tìm thấy đơn này: {data['error']}."
        else:
            text = (f"Đơn {data['order_id']} hiện '{data['status']}', vị trí: {data['location']} "
                    f"(cập nhật lúc {data['updated_at']}).")
        return json.dumps({"type": "answer", "text": text}, ensure_ascii=False)

    # Harness báo không thực hiện được → xin lỗi
    if harness_notes:
        return json.dumps({"type": "answer",
                           "text": "Xin lỗi, hiện mình chưa tra được đơn. Mình chuyển nhân viên hỗ trợ nhé."},
                          ensure_ascii=False)

    # Chưa có dữ liệu → nếu mô tả tool có nhắc tới "đơn hàng" thì đề xuất gọi tool
    order = re.search(r"ORD-\d+", prompt)
    for line in system.splitlines():
        if line.startswith("- ") and "đơn hàng" in line and order:
            tool_name = line[2:].split(":")[0]
            return json.dumps({"type": "tool_call", "tool": tool_name,
                               "args": {"order_id": order.group()}})

    # Không thấy tool phù hợp → trả lời luôn (đoán)
    return json.dumps({"type": "answer", "text": "Đơn ORD-001 của bạn đang trên đường giao nhé."},
                      ensure_ascii=False)

# --- Test tạm ---
# system_with_tool = (GOOD_CONFIG.instructions + "\n\nTOOL CÓ SẴN:\n- lookup_order: "
#                     + GOOD_CONFIG.tool_descriptions["lookup_order"])
# question_prompt = "Câu hỏi của khách: " + QUESTION

# print("1.", fake_model(system_with_tool, question_prompt, True))

# observation = lookup_order_fresh({"order_id": "ORD-001"})
# prompt_with_obs = question_prompt + "\nOBSERVATION: " + json.dumps(observation, ensure_ascii=False)
# print("2.", fake_model(system_with_tool, prompt_with_obs, True))

# print("3.", fake_model(DECLARATION_ONLY_CONFIG.instructions, question_prompt, False))

# print("4.", gemini_model("Trả lời đúng 1 câu ngắn.", "Xin chào, bạn là ai?", False))


# ===== VÙNG 3: HARNESS / RUNTIME =====
@dataclass
class RuntimeSetup:
    name: str
    supports_tools: bool                              # runtime có biết xử lý tool call không
    integrations: dict[str, Callable[[dict], dict]]   # tên tool → hàm nối thật tới Environment
    allowed_tools: set[str]                           # quyền: runtime mới là nơi enforce
    max_steps: int = 3


@dataclass
class RunResult:
    answer: str
    trace: list[dict]    # bản ghi lượt chạy: bằng chứng về những gì THẬT SỰ đã xảy ra


TOOL_PROTOCOL = """Mỗi lượt, trả về DUY NHẤT một JSON theo một trong hai dạng:
{"type": "tool_call", "tool": "<tên tool>", "args": {...}}
{"type": "answer", "text": "<câu trả lời cho khách>"}
Dòng OBSERVATION là dữ liệu thật hệ thống nhận được từ tool. Dòng HARNESS là thông báo của hệ thống."""

# Những câu "tự thuật" kiểu "mình đã kiểm tra", cần đối chiếu với trace
CLAIM_PATTERN = re.compile(r"đã (kiểm tra|tra cứu|tra|xem|check)|theo (hệ thống|dữ liệu)",
                           re.IGNORECASE)


def build_input(config: AgentConfig, question: str, notes: list[str],
                with_tools: bool) -> tuple[str, str]:
    """Harness CHUẨN BỊ INPUT: ghép instructions + mô tả tool + câu hỏi + state."""
    system = config.instructions
    if with_tools and config.tool_descriptions:
        tool_lines = "\n".join(f"- {name}: {desc}"
                               for name, desc in config.tool_descriptions.items())
        system += f"\n\nTOOL CÓ SẴN:\n{tool_lines}\n\n{TOOL_PROTOCOL}"
    elif with_tools:
        system += f"\n\n{TOOL_PROTOCOL}"

    prompt = f"Câu hỏi của khách: {question}"
    if notes:
        prompt += "\n" + "\n".join(notes)
    return system, prompt


def parse_model_output(raw: str) -> dict | None:
    """Harness KIỂM TRA OUTPUT: phải là JSON đúng dạng, sai thì trả về None."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict) or data.get("type") not in ("tool_call", "answer"):
        return None
    return data


def decide_dispatch(tool: str, runtime: RuntimeSetup) -> str:
    """Harness QUYẾT ĐỊNH DISPATCH: chỗ duy nhất biến đề xuất thành lời gọi thật."""
    if tool not in runtime.allowed_tools:
        return "blocked_by_policy"     # không được phép (dù configuration có khai báo)
    if tool not in runtime.integrations:
        return "no_integration"        # được phép nhưng không có dây nối tới dữ liệu
    return "dispatch"


def flag_unverified_claim(answer: str, trace: list[dict]) -> None:
    """Harness đối chiếu lời tự thuật của model với bằng chứng trong trace."""
    has_observation = any(event["event"] == "observation" for event in trace)
    if CLAIM_PATTERN.search(answer) and not has_observation:
        trace.append({"zone": "runtime", "event": "unverified_claim",
                      "note": "Model nói như đã tra, nhưng không có observation nào"})


def run_agent(question: str, config: AgentConfig, model: Callable,
              runtime: RuntimeSetup) -> RunResult:
    trace: list[dict] = []
    notes: list[str] = []      # STATE: những gì lượt chạy cần nhớ giữa các bước

    # Runtime chỉ biết text: lấy luôn output của model làm câu trả lời
    if not runtime.supports_tools:
        trace.append({"zone": "runtime", "event": "no_tool_path",
                      "note": "Runtime chỉ xử lý text, không có đường dispatch tới Environment"})
        system, prompt = build_input(config, question, notes, with_tools=False)
        answer = model(system, prompt, False)
        trace.append({"zone": "model", "event": "answer", "text": answer})
        flag_unverified_claim(answer, trace)
        return RunResult(answer, trace)

    # Vòng lặp: model đề xuất → runtime quyết định → environment trả dữ liệu → lặp lại
    for step in range(1, runtime.max_steps + 1):
        system, prompt = build_input(config, question, notes, with_tools=True)
        raw = model(system, prompt, True)
        output = parse_model_output(raw)

        if output is None:
            trace.append({"zone": "runtime", "event": "invalid_output", "raw": raw[:200]})
            notes.append("HARNESS: output vừa rồi không đúng JSON, hãy trả lại đúng format.")
            continue

        if output["type"] == "answer":
            answer = str(output.get("text", ""))
            trace.append({"zone": "model", "event": "answer", "text": answer})
            flag_unverified_claim(answer, trace)
            return RunResult(answer, trace)

        # Output là ĐỀ XUẤT gọi tool: chỉ là dữ liệu, chưa có gì chạy cả
        tool = str(output.get("tool", ""))
        args = output.get("args") or {}
        trace.append({"zone": "model", "event": "proposal", "tool": tool, "args": args})

        decision = decide_dispatch(tool, runtime)
        trace.append({"zone": "runtime", "event": "dispatch_decision",
                      "tool": tool, "decision": decision})

        if decision == "dispatch":
            data = runtime.integrations[tool](args)          # LỜI GỌI THẬT
            trace.append({"zone": "environment", "event": "observation", "data": data})
            notes.append("OBSERVATION: " + json.dumps(data, ensure_ascii=False))
        else:
            notes.append(f"HARNESS: hệ thống không thực hiện '{tool}' ({decision}).")

    trace.append({"zone": "runtime", "event": "max_steps"})
    return RunResult("[Dừng vì vượt quá số bước cho phép]", trace)


    # --- Test tạm ---
# full_runtime = RuntimeSetup("có integration, có quyền", True,
#                             {"lookup_order": lookup_order_fresh}, {"lookup_order"})
# text_only_runtime = RuntimeSetup("chỉ xử lý text", False, {}, set())
# blocked_runtime = RuntimeSetup("có integration, KHÔNG có quyền", True,
#                                {"lookup_order": lookup_order_fresh}, set())

# test_cases = [
#     ("A. Hệ thống đầy đủ", GOOD_CONFIG, full_runtime),
#     ("B. Chỉ khai báo, không integration", DECLARATION_ONLY_CONFIG, text_only_runtime),
#     ("C. Runtime chặn", GOOD_CONFIG, blocked_runtime),
# ]

# for title, config, runtime in test_cases:
#     result = run_agent(QUESTION, config, fake_model, runtime)
#     print(f"\n{title}\n  Trả lời: {result.answer}")
#     for event in result.trace:
#         print("   ", event)

# ===== CHẨN ĐOÁN: từ triệu chứng → vùng cần hỏi trước =====
def diagnose(result: RunResult, trace_visible: bool) -> list[str]:
    notes: list[str] = []
    claims_checked = bool(CLAIM_PATTERN.search(result.answer))

    # Goc nhin nguoi dung: chi thay cau tra loi, khong thay trace
    if not trace_visible:
        notes.append("Bạn chỉ thấy câu trả lời, không thấy dấu vết gọi tool.")
        if claims_checked:
            notes.append("Câu 'đã kiểm tra' là output của model, CHƯA PHẢI bằng chứng.")
        notes.append("Còn bỏ ngỏ 3 khả năng: (1) model không đề xuất tra -> Model/Configuaration; "
        "(2) có đề xuất nhưng runtime không dispath -> Harness/runtime; "
        "(3) không có intergration."
        )
        notes.append("KẾT LUẬN: chưa đủ bằng chứng để chọn root cause 'Không thấy' chưa phải 'không có'. ")
        return notes
    
    events = [event["event"] for event in result.trace ]
    decisions = [event["decision"] for event in result.trace if event["event"] == "dispatch_decision"]
    observations = [event["data"] for event in result.trace if event["event"] == "observation"]

    if "no_tool_path" in events:
        notes.append("Runtime không có đường gọi tool tới dữ liệu -> thiếu intergration. "
        "Đổi model không bù được phần này."
        )
    elif "proposal" not in events:
        notes.append("Model không đề xuất gọi tool -> hỏi vung Model + Configuration trước"
        "(mô tả tool có đủ rõ để model dùng không?)."
        )
    
    if "blocked_by_policy" in decisions:
        notes.append("Model có đề xuất nhưng Herness/runtime chặn -> xét quyền ở runtime. "
        "Configuration có khai báo tool cũng không cấp quyền.")
    
    if "no_intergration" in decisions:
        notes.append("Runtime cho phép nhưng không có intergration -> 'danh bạ có số, day chưa kéo'.")
    
    if "unverified_claim" in events:
        notes.append("Model đã nói như đã tra nhưng trace không có observation -> tự thuật không có bằng chứng.")

    for data in observations:
        if "error" in data:
            notes.append(f"Evironment trả lỗi: {data['error']}.")
            continue
        updated_at = datetime.strptime(data['updated_at'], "%Y-%m-%d %H:%M")
        age_hours = (NOW - updated_at).total_seconds() / 3600

        if age_hours > STALE_AFTER_HOURS:
            notes.append(f"Có lượt tra THẬT, nhưng dữ liệu cập nhật cách đây {age_hours: .0f} giờ "
            "-> xet Evironment trước (nguồn dữ liệu cũ). Đổi model không làm dữ liệu mới lên."
            )
        if data['status'].lower() not in result.answer.lower():
            notes.append("Câu trả lời không chứa trạng thái lấy từ observation -> xét Harness. "
            "(kết quả có được đưa đúng vào input không) rồi tới Model."
            )
        elif age_hours <= STALE_AFTER_HOURS:
            notes.append("Có dispath thật, dữ liệu mới, câu trả lời khớp observation")
    return notes or ["Không có dấu hiệu bất thưởng trong trace."]


# ===== CÁC TÌNH HUỐNG: mỗi tình huống "làm hỏng" đúng một vùng =====

SCENARIOS = [
    {"title": "Hệ thống đầy đủ (hệ thống thứ nhất trong bài)",
     "config": GOOD_CONFIG,
     "runtime": RuntimeSetup("có integration, có quyền", True,
                             {"lookup_order": lookup_order_fresh}, {"lookup_order"})},
    {"title": "Chỉ có khai báo, không integration (hệ thống thứ hai)",
     "config": DECLARATION_ONLY_CONFIG,
     "runtime": RuntimeSetup("chỉ xử lý text", False, {}, set())},
     
    {"title": "Mô tả tool mơ hồ (vùng Configuration)",
     "config": VAGUE_CONFIG,
     "runtime": RuntimeSetup("có integration, có quyền", True,
                             {"tool_x": lookup_order_fresh}, {"tool_x"})},
    {"title": "Runtime không cho phép tool (vùng Harness/runtime)",
     "config": GOOD_CONFIG,
     "runtime": RuntimeSetup("có integration, KHÔNG có quyền", True,
                             {"lookup_order": lookup_order_fresh}, set())},
    {"title": "Nguồn dữ liệu cũ (vùng Environment)",
     "config": GOOD_CONFIG,
     "runtime": RuntimeSetup("integration tới nguồn cũ", True,
                             {"lookup_order": lookup_order_stale}, {"lookup_order"})},
]
    
ZONE_LABELS = {"model": "🧠 MODEL      ", "runtime": "⚙️  RUNTIME    ",
               "environment": "🗄️  ENVIRONMENT"}


def print_trace(trace: list[dict]) -> None:
    for event in trace:
        details = {key: value for key, value in event.items() if key not in ("zone", "event")}
        print(f"    {ZONE_LABELS[event['zone']]} {event['event']:<18} "
              f"{json.dumps(details, ensure_ascii=False)[:150]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", type=int, help="chỉ chạy tình huống số N (1-5)")
    parser.add_argument("--model", default=llm_module.MODEL,
                        help="tên model Gemini, hoặc 'fake' để dùng model giả")
    parser.add_argument("--hide-trace", action="store_true",
                        help="đứng ở góc nhìn người dùng: không thấy trace")
    parser.add_argument("--question", default=QUESTION)
    args = parser.parse_args()

    if args.model == "fake":
        model = fake_model
    else:
        llm_module.MODEL = args.model      # "đổi model" chỉ là đổi đúng dòng này
        model = gemini_model

    if args.scenario:
        picked = [(args.scenario, SCENARIOS[args.scenario - 1])]
    else:
        picked = list(enumerate(SCENARIOS, start=1))

    print(f"Model: {args.model}   |   Câu hỏi: {args.question}")
    for number, scenario in picked:
        print(f"\n{'=' * 78}\nTình huống {number}: {scenario['title']}")
        print(f"  Configuration: {scenario['config'].name}   |   Runtime: {scenario['runtime'].name}")

        result = run_agent(args.question, scenario["config"], model, scenario["runtime"])
        print(f"\n  💬 Agent trả lời: {result.answer.strip()}")

        if not args.hide_trace:
            print("\n  📜 Trace (bản ghi lượt chạy):")
            print_trace(result.trace)

        print("\n  🔍 Chẩn đoán:")
        for note in diagnose(result, trace_visible=not args.hide_trace):
            print(f"    • {note}")


if __name__ == "__main__":
    main()
    
    