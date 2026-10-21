from dotenv import load_dotenv
from google import genai

load_dotenv("../../.env")
client = genai.Client()

LABELS = ["hoàn tiền", "lỗi kỹ thuật", "khác"]

def classify(ticket: str) -> str:
    # TODO 1: gọi model, bảo nó CHỈ trả về đúng một trong LABELS
    response = client.models.generate_content(model="gemini-3.5-flash-lite", contents="CHỈ trả về đúng một trong LABELS: " + ", ".join(LABELS) + "\nTicket: " + ticket)
    # TODO 2: .strip().lower() kết quả
    # TODO 3: nếu không nằm trong LABELS -> return "khác"
    result = response.text.strip().lower()
    if result in LABELS:
        return result
    return "khác"

def handle_refund(ticket): print("-> kiểm tra đơn, đối chiếu chính sách, gửi email")
def handle_tech(ticket):   print("-> thu thập thông tin, tạo issue")
def handle_other(ticket):  print("-> chuyển cho nhân viên")

def run(ticket: str):
    label = classify(ticket)
    print("Nhãn:", label)
    # TODO 4: if/elif gọi đúng handler
    if label == "hoàn tiền":
        handle_refund(ticket)
    elif label == "lỗi kỹ thuật":
        handle_tech(ticket)
    else:
        handle_other(ticket)

if __name__ == "__main__":
    for t in ["Tôi muốn trả hàng lấy lại tiền",
              "App bị đứng khi bấm thanh toán",
              "Cho mình hỏi giờ làm việc"]:
        print("Ticket:", t)
        run(t)