import os
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def chat(system_prompt, user_message, json_mode=False):
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        response_mime_type="application/json" if json_mode else "text/plain",
    )
    response = client.models.generate_content(
        model=MODEL,
        contents=user_message,
        config=config,
    )
    return response.text


if __name__ == "__main__":
    print(chat("Answer briefly.", "Hello!"))