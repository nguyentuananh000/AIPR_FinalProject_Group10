"""Run one RAG question and save a readable retrieval/generation trace."""

import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.llm_client import LLMClient
from src.rag.chunker import PolicyChunker
from src.rag.hybrid_retriever import HybridRetriever


QUESTION = "Hạn mức thanh toán chi phí ăn uống mỗi ngày cho nhân viên đi công tác là bao nhiêu?"
TOP_K = 3


def main() -> None:
    corpus_dir = PROJECT_ROOT / "data" / "corpus"
    prompt_path = PROJECT_ROOT / "prompts" / "rag_system.txt"

    if not corpus_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy thư mục corpus: {corpus_dir}")
    if not prompt_path.is_file():
        raise FileNotFoundError(f"Không tìm thấy prompt RAG: {prompt_path}")

    chunks = PolicyChunker().chunk_corpus(corpus_dir)
    retriever = HybridRetriever(chunks)
    retrieved = retriever.retrieve(
        query=QUESTION,
        top_k=TOP_K,
        mode="hybrid",
        metadata_filter={"status": "active"},
    )

    context = "\n\n".join(
        f"[{chunk.doc_id} — {chunk.metadata.get('section_title', '')}]\n{chunk.content}"
        for chunk, _score in retrieved
    )
    rag_template = prompt_path.read_text(encoding="utf-8")
    system_prompt = (
        rag_template.replace("{context}", context)
        .replace("{question}", QUESTION)
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": QUESTION},
    ]

    llm = LLMClient()
    answer, usage = llm.chat(messages, temperature=0.0)
    timestamp = datetime.now().astimezone().isoformat(timespec="seconds")

    lines = [
        "=======================================================",
        "REAL RUN TRACE LOG — AIPR FINAL PROJECT GROUP 10",
        "=======================================================",
        f"Query: {QUESTION}",
        f"Timestamp: {timestamp}",
        "",
        "--- [RAG RETRIEVAL STAGE] ---",
        f"Total Chunks Retrieved: {len(retrieved)}",
    ]

    for rank, (chunk, score) in enumerate(retrieved, start=1):
        section = chunk.metadata.get("section_title", "")
        lines.append(
            f"Rank {rank}: [{chunk.doc_id}] {section} | Score={score:.4f}"
        )

    lines.extend(
        [
            "",
            "--- [LLM GENERATION STAGE] ---",
            f"Model: {usage.model}",
            f"Prompt Tokens: {usage.prompt_tokens}",
            f"Total Tokens: {usage.total_tokens}",
            f"Latency: {usage.latency_seconds:.3f}s",
            "",
            "--- [GENERATED ANSWER] ---",
            answer,
            "=======================================================",
        ]
    )
    trace = "\n".join(lines)

    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"rag_trace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    log_path.write_text(trace + "\n", encoding="utf-8")

    print(trace)
    print(f"\nTrace saved to: {log_path}")


if __name__ == "__main__":
    main()
