from llm import chat
from tools import lookup_order, get_policy

def handle_order_question(order_id: str, message: str):
    order = lookup_order(order_id=order_id)
    policy = get_policy(order["status"])
    message = (
        f"Khách hàng nói: {message} \n"
        f"Thời gian giao hàng dự kiến: {order['eta']} \n"
        f"Chính sách: {policy}"
    )

    return chat(
        "Bạn là nhân viên hỗ trợ khách hàng. Hãy trả lời ngắn gọn, "
        "phù hợp với giọng điệu của khách hàng, "
        "và chỉ sử dụng những thông tin được cung cấp.",
        message
    )

if __name__ == "__main__":
    messages = [
        "Đơn ORD-001 sao giao trễ vậy, tôi bực quá rồi!",
        "Cho mình hỏi đơn ORD-001 bao giờ tới nhé?",
        "Chào shop, đơn ORD-001 hình như hơi chậm ạ",
    ]
    for message in messages:
        print("CUSTOMER:", message)
        print("BOT     :", handle_order_question("ORD-001", message))
        print()
