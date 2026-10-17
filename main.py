"""
Module: main
Mô tả: Điểm khởi chạy duy nhất (Single Entry Point) của toàn bộ dự án AIPR Group 10.
Đáp ứng Yêu cầu 2.1: Chạy bằng 1 lệnh duy nhất trên máy Giảng viên.

Hệ thống kết hợp trọn vẹn 3 tầng:
1. Evidence Layer: HybridRetriever (RAG) đối soát văn bản quy chế (DOC0001 - DOC0005).
2. Reasoning Layer: ReAct Agent Loop suy luận kiểm toán và tuân thủ quy tắc Grounding/Calibration.
3. Action Layer: MCP Client/Server qua stdio đọc dữ liệu, ghi quyết định và tự động xác minh (Verify).
"""

import sys
import os
import json
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Reconfigure stdout/stderr sang UTF-8 để không bị lỗi mã hóa font trên Windows Console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Đảm bảo đường dẫn import hoạt động trên mọi môi trường
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv()

from src.core.llm_client import LLMClient
from src.rag.chunker import PolicyChunker
from src.rag.hybrid_retriever import HybridRetriever
from src.mcp.client import run_with_mcp


def print_banner():
    banner = r"""
========================================================================
   AIPR FINAL PROJECT — BUSINESS TRAVEL EXPENSE AUDIT AGENT (T2)
                       GROUP 10 — HCMUTE
========================================================================
  • RAG Engine: Section-based Chunking + Hybrid Search (BM25 + Vector)
  • Agent Loop: ReAct (Thought -> Action -> Observation) with Safe Parser
  • Action Layer: Model Context Protocol (MCP) Server/Client via stdio
========================================================================
"""
    print(banner)


def audit_claim_with_rag(claim_id: str, retriever: HybridRetriever, llm: LLMClient) -> str:
    """
    Quy trình kiểm toán hoàn chỉnh cho một hồ sơ chi phí (Claim ID):
    1. Đọc tệp dữ liệu claims để lấy thông tin sơ bộ các khoản chi.
    2. Dùng RAG HybridRetriever truy xuất các điều khoản quy định tương ứng.
    3. Ghép Context quy chế vào ReAct Agent.
    4. ReAct Agent gọi MCP Tool đọc chi tiết, ra quyết định kiểm toán và tự động verify.
    """
    claims_db_path = PROJECT_ROOT / "data" / "audit_claims_db.json"
    if not claims_db_path.exists():
        return f"Lỗi: Không tìm thấy cơ sở dữ liệu {claims_db_path}"

    claims_data = json.loads(claims_db_path.read_text(encoding="utf-8"))
    target_claim = None
    for c in claims_data:
        if c.get("claim_id", "").upper() == claim_id.strip().upper():
            target_claim = c
            break

    if not target_claim:
        return f"Lỗi: Không tìm thấy hồ sơ chi phí có mã '{claim_id}' trong cơ sở dữ liệu."

    print(f"\n🔍 [1/3] Đã tìm thấy hồ sơ chi phí: {target_claim['claim_id']} ({target_claim['employee_name']} - {target_claim['department']})")
    print(f"    Tổng số tiền đề nghị thanh toán: ${sum(item.get('amount', 0) for item in target_claim.get('expenses', []))}")

    # Truy xuất các điều khoản liên quan qua RAG
    query = f"Quy định về hạn mức chi tiêu ăn uống, khách sạn, taxi và thẩm quyền duyệt chi phí công tác {target_claim['department']}"
    retrieved_items = retriever.retrieve(query, top_k=3, mode="hybrid", metadata_filter={"status": "active"})
    
    context_text = "\n\n".join(
        [f"[{c.doc_id} — {c.metadata.get('section_title', '')}]\n{c.content}" for c, _ in retrieved_items]
    )
    print(f"📚 [2/3] Đã truy xuất {len(retrieved_items)} điều khoản căn cứ pháp lý từ RAG:")
    for c, score in retrieved_items:
        print(f"    - {c.doc_id}: {c.metadata.get('section_title', '')} (Điểm Hybrid: {score:.3f})")

    # Xây dựng System Prompt kết hợp căn cứ RAG và hướng dẫn Agent
    system_prompt = f"""Bạn là Kiểm toán viên Trưởng của tập đoàn Acme Corp.
Nhiệm vụ của bạn là kiểm toán hồ sơ chi phí công tác mã '{claim_id}'.

CĂN CỨ PHÁP LÝ QUY CHẾ HIỆN HÀNH (RAG Context):
{context_text}

QUY TRÌNH KIỂM TOÁN BẮT BUỘC (ReAct Pattern):
1. Dùng tool `get_claim_details` với `{{"claim_id": "{claim_id}"}}` để đọc chi tiết các hóa đơn và chữ ký phê duyệt.
2. Đối chiếu từng khoản chi với Căn cứ pháp lý ở trên (tiền ăn <= $50/ngày, khách sạn <= $120/đêm, taxi sân bay <= $35/chuyến, thẩm quyền duyệt <= $500 là Team Lead, <= $2,000 là Department Head, > $2,000 là C-level).
3. Đưa ra quyết định:
   - "APPROVED": Nếu hợp lệ toàn bộ.
   - "ADJUSTED": Nếu có khoản vượt định mức hoặc mất hóa đơn cần giảm trừ.
   - "REJECTED": Nếu chứa chi phí cấm (rượu bia, du lịch cá nhân).
   - "ESCALATED": Nếu thiếu chữ ký cấp có thẩm quyền tương ứng với số tiền.
4. Dùng tool `submit_audit_decision` để lưu quyết định vào hệ thống: `{{"claim_id": "{claim_id}", "status": "<STATUS>", "notes": "<Lý do>", "approved_amount": <Số_tiền>}}`.
5. Sau khi lưu, hệ thống sẽ tự động đối soát lại qua `get_claim_status`.
6. Trả về kết luận cuối cùng bằng:
Final Answer: <Tóm tắt kết quả kiểm toán, số tiền được duyệt, căn cứ điều khoản trích dẫn>.

LƯU Ý ĐỊNH DẠNG ACTION:
Luôn xuất Action theo đúng cú pháp chữ: Action: tên_tool({{"tham_số": "giá_trị"}})
"""

    print(f"[3/3] Đang khởi chạy ReAct Agent Loop kết nối MCP Server...")
    question = f"Hãy tiến hành kiểm toán đầy đủ cho hồ sơ chi phí {claim_id}."
    
    # Chạy vòng lặp ReAct qua MCP Client
    result = asyncio.run(run_with_mcp(
        llm_client=llm.client,
        question=question,
        system_prompt=system_prompt,
        model=llm.model,
    ))
    return result


def query_policy_rag(query_text: str, retriever: HybridRetriever, llm: LLMClient) -> str:
    """Hỏi đáp quy chế chi tiêu công tác bằng RAG (Hybrid Search)."""
    retrieved_items = retriever.retrieve(query_text, top_k=3, mode="hybrid", metadata_filter={"status": "active"})
    context_text = "\n\n".join(
        [f"[{c.doc_id} — {c.metadata.get('section_title', '')}]\n{c.content}" for c, _ in retrieved_items]
    )

    prompt_path = PROJECT_ROOT / "prompts" / "rag_system.txt"
    template = prompt_path.read_text(encoding="utf-8")
    system_content = template.replace("{context}", context_text).replace("{question}", query_text)

    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": query_text},
    ]

    answer, usage = llm.chat(messages, temperature=0.0)
    print(f"\n[Trích dẫn căn cứ]:")
    for c, score in retrieved_items:
        print(f"  • {c.doc_id} - {c.metadata.get('section_title')} (Điểm: {score:.3f})")
    print(f"[Đo lường USAGE]: {usage.total_tokens} tokens | Độ trễ: {usage.latency_seconds}s")
    return answer


def main():
    parser = argparse.ArgumentParser(description="AIPR Final Project Group 10 — Business Travel Expense Audit Agent")
    parser.add_argument("--claim", type=str, help="Mã hồ sơ chi phí cần kiểm toán (ví dụ: CLM001, CLM002, CLM003)")
    parser.add_argument("--query", type=str, help="Câu hỏi tra cứu quy chế công tác phí bằng RAG")
    parser.add_argument("--eval", action="store_true", help="Chạy đánh giá tự động toàn diện trên testset")
    args = parser.parse_args()

    print_banner()

    # Khởi tạo các thành phần cốt lõi
    print("Đang nạp kho quy chế chính sách và khởi tạo bộ truy xuất RAG...")
    chunker = PolicyChunker()
    chunks = chunker.chunk_corpus(PROJECT_ROOT / "data" / "corpus")
    retriever = HybridRetriever(chunks)
    llm = LLMClient()
    print("Hệ thống đã sẵn sàng hoạt động!\n")

    # Xử lý cờ dòng lệnh nếu có
    if args.claim:
        result = audit_claim_with_rag(args.claim, retriever, llm)
        print("\n" + "="*50)
        print("KẾT QUẢ KIỂM TOÁN CUỐI CÙNG:")
        print("="*50)
        print(result)
        return

    if args.query:
        print(f"❓ Câu hỏi: {args.query}")
        answer = query_policy_rag(args.query, retriever, llm)
        print("\nCâu trả lời:")
        print(answer)
        return

    if args.eval:
        from src.eval.run_eval import main as run_eval_main
        run_eval_main()
        return

    # Chế độ tương tác Menu dòng lệnh trực quan
    while True:
        print("-" * 55)
        print("VUI LÒNG CHỌN CHỨC NĂNG BẠN MUỐN THỰC HIỆN:")
        print("1. Kiểm toán hồ sơ chi phí (ReAct Agent + MCP + RAG)")
        print("2. Tra cứu quy chế chính sách (RAG Q&A)")
        print("3. Chạy đánh giá tự động toàn diện (Run Benchmark Eval)")
        print("4. Thoát chương trình")
        print("-" * 55)
        
        choice = input("Nhập lựa chọn của bạn (1-4): ").strip()

        if choice == "1":
            claim_id = input("Nhập mã claim cần kiểm toán (mặc định: CLM-101): ").strip() or "CLM-101"
            result = audit_claim_with_rag(claim_id, retriever, llm)
            print("\n" + "="*50)
            print("KẾT QUẢ KIỂM TOÁN:")
            print("="*50)
            print(result)
        elif choice == "2":
            q = input("Nhập câu hỏi quy chế (ví dụ: Hạn mức tiền ăn mỗi ngày là bao nhiêu?): ").strip()
            if q:
                ans = query_policy_rag(q, retriever, llm)
                print("\nTrả lời:\n" + ans)
        elif choice == "3":
            from src.eval.run_eval import main as run_eval_main
            run_eval_main()
        elif choice == "4":
            print("Cảm ơn bạn đã sử dụng hệ thống. Chúc buổi bảo vệ đồ án thành công rực rỡ!")
            break
        else:
            print("Lựa chọn không hợp lệ, vui lòng chọn từ 1 đến 4.")


if __name__ == "__main__":
    main()
