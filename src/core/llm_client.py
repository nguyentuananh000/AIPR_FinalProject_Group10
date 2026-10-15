import os
import sys
import time
import random
import logging
from pathlib import Path
from typing import Any
from dotenv import load_dotenv
from groq import Groq, RateLimitError, APIConnectionError, APIStatusError

from src.models.eval_result import UsageLog

load_dotenv()

#cấu hình logger 
logger = logging.getLogger("LLMClient")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stderr)
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


def loaf_promt_template(filename: str) -> str:
    """đọc nội dung file prompt từ thư mục prompts/"""
    prompt_path = Path(__file__).parent[2] / "prompts" / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Không tìm thấy file prompt: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")

class LLMClient:
    """
    Wrapper gọi LLM API (Groq) tích hợp:
    1. Timeout chống treo kết nối.
    2. Exponential Backoff Retry cho các lỗi mạng và Rate Limit (429, 5xx).
    3. Phân loại lỗi HTTP (không retry lỗi 4xx như sai key hay sai tham số).
    4. Tự động đo đạc UsageLog (tokens, latency).
    """

    def __init__(
        self, model: str | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
    ):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            logger.warning("Chưa tìm thấy API_KEY")

        self.model = model or os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
        self.timeout = timeout
        self. max_retries = max_retries
        self.client = Groq(api_key=api_key, timeout=self.timeout)

    def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
    ) -> tuple[str, UsageLog]:
        """
        Gửi request tới LLM với cơ chể retry exponential backoff.
        trả về tuple gồm: (nội_dung_trả_lời, đối_tượng_UsageLog)
        """
        for attempt in range(self.max_retries + 1):
            start_time = time.time()
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                )
                elapsed = round(time.time() - start_time, 3)

                content = (response.choices[0].message.content or "").strip()
                prompt_tok = response.usage.prompt_tokens if response.usage else 0
                comp_tok = response.usage.completion_tokens if response.usage else 0

                usage = UsageLog(
                    calls=1,
                    prompt_tokens=prompt_tok,
                    total_tokens=prompt_tok + comp_tok,
                    max_prompt_tokens=prompt_tok,
                    latency_seconds=elapsed,
                    model=self.model,
                )
                return content, usage

            except (RateLimitError, APIConnectionError) as err:
                #nhóm lỗi tạm thời (429 rate limit hoặc đứt kết nối mạng) -> cần retry
                if attempt < self.max_retries:
                    delay = ( 2 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(
                        f"Lỗi tạm thời ({type(err).__name__}). Thử lại lần {attempt+1}/{self.max_retries} sau {delay:.2f}s..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"Đã hết {self.max.retries} lần thử lại. Lỗi: {err}")
                    raise

            except APIStatusError as err:
                # Phân loại mã lỗi HTTP:
                # - 5xx (Server Error): Lỗi phía máy chủ LLM -> CẦN RETRY
                # - 4xx (Client Error: 400 Bad Request, 401 Unauthorized): Lỗi code/key -> KHÔNG RETRY
                logger.error(f"Lỗi HTTP Status {err.status_code}: {err.message}")
                if err.status_code >= 500 and attempt < self.max_retries:
                    delay = (2 ** attempt) + random.uniform(0.1, 1.0)
                    logger.warning(f"Lỗi máy chủ 5xx. Thử lại sau {delay:.2f}s...")
                    time.sleep(delay)
                else:
                    raise

        raise RuntimeError("Không thể kết nối LLM sau nhiều lần thử lại.") 
        