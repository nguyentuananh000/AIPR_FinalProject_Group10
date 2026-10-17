"""
Script tự động sinh 3 run trace thực tế để lưu vào thư mục logs/
Đáp ứng Yêu cầu 2.10: Có ít nhất >= 3 run trace thật.
"""

import sys
from pathlib import Path
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from datetime import datetime
from src.core.llm_client import LLMClient
from src.rag.chunker import PolicyChunker
from src.rag.hybrid_retriever import HybridRetriever

def generate_traces():
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    print("⏳ Đang khởi tạo RAG Retriever...")
    chunker = PolicyChunker()
    chunks = chunker.chunk_corpus("data/corpus")
    retriever = HybridRetriever(chunks)
    llm = LLMClient()
    template = Path("prompts/rag_system.txt").read_text(encoding="utf-8")

    test_queries = [
        (
            "trace_01_query_meal_limit.txt",
            "Hạn mức thanh toán chi phí ăn uống mỗi ngày cho nhân viên đi công tác là bao nhiêu?"
        ),
        (
            "trace_02_query_hotel_limit.txt",
            "Tiêu chuẩn phòng khách sạn cho nhân viên thông thường tại các thành phố lớn là bao nhiêu một đêm?"
        ),
        (
            "trace_03_query_no_answer_calibration.txt",
            "Công ty có hỗ trợ chi phí mua quà lưu niệm cho người thân khi nhân viên đi công tác nước ngoài không?"
        )
    ]

    for filename, query in test_queries:
        print(f"▶ Đang tạo trace: {filename}...")
        items = retriever.retrieve(query, top_k=3, mode="hybrid", metadata_filter={"status": "active"})
        context_parts = []
        for c, _ in items:
            sec = c.metadata.get("section_title", "")
            context_parts.append(f"[{c.doc_id} — {sec}]\n{c.content}")
        ctx = "\n\n".join(context_parts)

        sys_prompt = template.replace("{context}", ctx).replace("{question}", query)
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": query}
        ]

        ans, usage = llm.chat(messages, temperature=0.0)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trace_text = (
            f"=======================================================\n"
            f"REAL RUN TRACE LOG — AIPR FINAL PROJECT GROUP 10\n"
            f"=======================================================\n"
            f"Query: {query}\n"
            f"Timestamp: {now_str}\n\n"
            f"--- [RAG RETRIEVAL STAGE] ---\n"
            f"Total Chunks Retrieved: {len(items)}\n"
        )
        for rank, (c, score) in enumerate(items, 1):
            trace_text += f"Rank {rank}: [{c.doc_id}] {c.metadata.get('section_title')} | Score={score:.4f}\n"

        trace_text += (
            f"\n--- [LLM GENERATION STAGE] ---\n"
            f"Model: {usage.model}\n"
            f"Prompt Tokens: {usage.prompt_tokens}\n"
            f"Total Tokens: {usage.total_tokens}\n"
            f"Latency: {usage.latency_seconds:.3f}s\n\n"
            f"--- [GENERATED ANSWER] ---\n"
            f"{ans}\n"
            f"=======================================================\n"
        )

        (logs_dir / filename).write_text(trace_text, encoding="utf-8")
        print(f"✅ Đã lưu thành công: {logs_dir / filename}")

if __name__ == "__main__":
    generate_traces()
