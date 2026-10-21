from dotenv import load_dotenv
from google import genai

load_dotenv("../../.env")
client = genai.Client()

chat = """Khách: đơn của tôi chưa tới
Nhân viên: bạn cho mình mã đơn nhé
Khách: 5000"""

# response = client.models.generate_content(model="gemini-3.5-flash-lite", contents="Tóm tắt: " + chat)
# print(response.text)