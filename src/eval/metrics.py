"""
Module: src.eval.metrics
Mô tả: Đo lường chất lượng hệ thống RAG theo chuẩn RAGAS.
Gồm 3 chỉ số:
1. Faithfulness (Tính trung thực / Không ảo giác): Số lượng claim đúng / Tổng số claim.
2. Answer Relevance (Độ liên quan câu trả lời): LLM Judge chấm YES/NO.
3. Retrieval Hit Rate (Độ chính xác truy xuất): Kiểm tra xem tài liệu kỳ vọng có nằm trong top kết quả trả về không.
"""

from pathlib import Path
from src.core.llm_client import LLMClient


def load_prompt(filename: str) -> str:
    """Đọc file prompt từ thư mục prompts/"""
    prompt_path = Path(__file__).resolve().parents[2] / "prompts" / filename
    if not prompt_path.exists():
        raise FileNotFoundError(f"Không tìm thấy prompt: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def calculate_hit_rate(retrieved_doc_ids: list[str], expected_doc_ids: list[str]) -> float:
    """
    Tính Retrieval Hit Rate:
    - Nếu câu hỏi không yêu cầu doc nào (câu no_answer), mặc định là 1.0.
    - Trả về 1.0 nếu có ít nhất 1 tài liệu mong đợi nằm trong kết quả tìm kiếm, ngược lại 0.0.
    """
    if not expected_doc_ids:
        return 1.0
    
    # Kiểm tra giao giữa 2 tập hợp mã văn bản
    retrieved_set = set(retrieved_doc_ids)
    expected_set = set(expected_doc_ids)
    
    return 1.0 if bool(retrieved_set & expected_set) else 0.0


def decompose_claims(llm: LLMClient, answer: str) -> list[str]:
    """
    Phân tách câu trả lời thành các tuyên bố đơn lẻ (Atomic Claims) theo chuẩn RAGAS Tuần 5.
    """
    # Nếu câu trả lời từ chối vì không có thông tin thì không cần phân tách
    if "không tìm thấy thông tin" in answer.lower():
        return [answer]

    template = load_prompt("claim_extraction.txt")
    prompt = template.format(answer=answer)
    
    response, _ = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    
    claims = [line.strip() for line in response.splitlines() if line.strip()]
    return claims if claims else [answer]


def evaluate_faithfulness(llm: LLMClient, answer: str, context: str) -> float:
    """
    Chấm điểm Faithfulness (Tính trung thực):
    - Phân tách câu trả lời thành các claims.
    - Dùng LLM Judge (temperature=0.0) kiểm tra từng claim có trong context không.
    - Điểm = Số claim YES / Tổng số claim.
    """
    # Trường hợp câu trả lời thông báo không tìm thấy thông tin
    if "không tìm thấy thông tin" in answer.lower():
        return 1.0

    claims = decompose_claims(llm, answer)
    if not claims:
        return 1.0

    template = load_prompt("judge_faithfulness.txt")
    supported_count = 0

    for claim in claims:
        prompt = template.format(context=context, claim=claim)
        verdict, _ = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        if "YES" in verdict.upper():
            supported_count += 1

    return round(supported_count / len(claims), 2)


def evaluate_relevance(llm: LLMClient, question: str, answer: str) -> float:
    """
    Chấm điểm Answer Relevance (Mức độ liên quan tới câu hỏi):
    - Dùng LLM Judge kiểm tra câu trả lời có trả lời đúng trọng tâm không.
    - Trả về 1.0 nếu YES, 0.0 nếu NO.
    """
    template = load_prompt("judge_relevance.txt")
    prompt = template.format(question=question, answer=answer)
    
    verdict, _ = llm.chat(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )
    return 1.0 if "YES" in verdict.upper() else 0.0