# Wrapper gọi Gemini dùng chung cho mọi bài
import os
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

# Đọc file .env ở thư mục agent-harness/

load_dotenv()
MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")

MIN_INTERVAL = 2.0        # số giây tối thiểu giữa 2 lần gọi (tránh lỗi 429 của free tier)
TIMEOUT_MS = 30_000       # mỗi request chờ tối đa 30 giây

_client = None
_last_call_time = 0.0


@dataclass
class LLMResult:
    text: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Thiếu GEMINI_API_KEY trong file .env")
        _client = genai.Client(api_key=api_key,
                               http_options=types.HttpOptions(timeout=TIMEOUT_MS))
    return _client


def call_llm(prompt: str, system: str | None = None, json_mode: bool = False,
             temperature: float = 0.2) -> LLMResult:
    """Gọi model đúng 1 lần. Không retry, không validate, vì đó là việc của harness."""
    global _last_call_time

    # Chờ cho đủ khoảng cách giữa 2 lần gọi
    wait = MIN_INTERVAL - (time.time() - _last_call_time)
    if wait > 0:
        time.sleep(wait)

    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        response_mime_type="application/json" if json_mode else None,
    )

    start = time.time()
    try:
        response = _get_client().models.generate_content(
            model=MODEL, contents=prompt, config=config)
    finally:
        _last_call_time = time.time()

    usage = response.usage_metadata
    return LLMResult(
        text=response.text or "",
        latency_ms=int((time.time() - start) * 1000),
        input_tokens=(usage.prompt_token_count or 0) if usage else 0,
        output_tokens=(usage.candidates_token_count or 0) if usage else 0,
    )