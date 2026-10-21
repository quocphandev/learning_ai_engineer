from llm import chat
from tools import ToolError, lookup_order, get_policy, set_failures


def lookup_order_with_retry(order_id, max_retries=2):
    for attempt in range(1, max_retries + 2):
        try:
            return lookup_order(order_id)
        except ToolError as error:
            print(f"  attempt {attempt} failed: {error}")
    return None


def handle_order_question(order_id, customer_message):
    order = lookup_order_with_retry(order_id)
    if order is None:
        return "Hiện chưa tra được đơn, bên em sẽ phản hồi trong 30 phút ạ."   # fallback

    policy = get_policy(order["status"])
    return chat(
        "Bạn là nhân viên hỗ trợ khách hàng. Hãy trả lời ngắn gọn.",
        f"Khách hàng: {customer_message}\n"
        f"Thời gian giao hàng dự kiến: {order['eta']}\n"
        f"Chính sách: {policy}",
    )


if __name__ == "__main__":
    for failures in (0, 1, 9):
        set_failures(failures)
        print(f"--- lookup fails {failures} time(s) ---")
        print(handle_order_question("ORD-001", "Đơn ORD-001 sao trễ vậy?"))
        print()