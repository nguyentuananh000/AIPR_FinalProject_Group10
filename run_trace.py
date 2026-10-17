import asyncio
import os

from dotenv import load_dotenv
from groq import Groq

from src.mcp.client import run_with_mcp


async def main():
    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Không tìm thấy GROQ_API_KEY trong file .env")

    model = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")
    llm_client = Groq(api_key=api_key)

    system_prompt = """
        Bạn là trợ lý kiểm toán chi phí công tác.
        Dùng các MCP tool được cung cấp để tra cứu hồ sơ.
        Khi cần tra cứu, hãy gọi MCP tool phù hợp được cung cấp trong yêu cầu.
        Không tự tạo tên tool hoặc tham số.
        Khi đã đủ thông tin, trả lời theo định dạng:
        Final Answer: câu trả lời
"""

    question = (
        "Kiểm tra hồ sơ CLM-103, tính tổng số tiền yêu cầu "
        "và cho biết trạng thái hiện tại. Chỉ đọc, không cập nhật hồ sơ."
    )

    answer = await run_with_mcp(
        llm_client=llm_client,
        question=question,
        system_prompt=system_prompt,
        model=model,
    )

    print("\nKẾT QUẢ CUỐI:")
    print(answer)


if __name__ == "__main__":
    asyncio.run(main())
