"""
Module: src.eval.run_eval
Mô tả: Script thực thi đánh giá tự động toàn diện hệ thống RAG trên 15 câu hỏi testset.
Tính năng:
1. Chạy thực nghiệm so sánh 2 cấu hình đối chứng: Dense Retrieval vs Hybrid Retrieval (+1 điểm thưởng).
2. Tự động chấm 3 chỉ số RAGAS: Faithfulness, Answer Relevance, Retrieval Hit Rate.
3. Đo đạc chi phí token và độ trễ (UsageLog) cho từng câu hỏi.
4. Xuất file số liệu chi tiết: eval_results.csv (+1 điểm thưởng).
5. Tự động vẽ và lưu biểu đồ cột trực quan hóa: eval_comparison.png (+1 điểm thưởng).
"""

import sys
import os
import json
import time
from pathlib import Path

# Thiết lập backend không hiển thị GUI cho matplotlib để chạy mượt mà trên mọi máy tính
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

# Đảm bảo import được module từ thư mục gốc dự án
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.llm_client import LLMClient
from src.models.eval_result import EvalSample, EvalResult, UsageLog
from src.rag.chunker import PolicyChunker
from src.rag.hybrid_retriever import HybridRetriever
from src.eval.metrics import (
    load_prompt,
    calculate_hit_rate,
    evaluate_faithfulness,
    evaluate_relevance,
)


def load_testset(filepath: Path | str) -> list[EvalSample]:
    """Tải danh sách 15 câu hỏi từ file tests/testset.jsonl."""
    samples = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                data = json.loads(line)
                samples.append(
                    EvalSample(
                        id=data["id"],
                        question=data["question"],
                        category=data["category"],
                        reference_answer=data["reference_answer"],
                        expected_doc_ids=data.get("expected_doc_ids", []),
                        expected_decision=data.get("expected_decision"),
                    )
                )
    return samples


def evaluate_configuration(
    samples: list[EvalSample],
    retriever: HybridRetriever,
    llm: LLMClient,
    mode: str,
    top_k: int = 3,
) -> list[dict]:
    """
    Chạy đánh giá toàn bộ testset với một cấu hình cụ thể ('dense' hoặc 'hybrid').
    """
    rag_template = load_prompt("rag_system.txt")
    records = []

    print(f"\n=======================================================")
    print(f"▶ ĐANG CHẠY THỰC NGHIỆM ĐÁNH GIÁ CẤU HÌNH: [{mode.upper()}]")
    print(f"=======================================================")

    for idx, sample in enumerate(samples, 1):
        print(f"[{idx}/{len(samples)}] Đang xử lý: {sample.id} - {sample.category}...")

        # 1. Truy xuất tài liệu với bộ lọc metadata status=active
        retrieved_items = retriever.retrieve(
            query=sample.question,
            top_k=top_k,
            mode=mode,
            metadata_filter={"status": "active"},
        )

        retrieved_docs = [c.doc_id for c, _ in retrieved_items]
        context_text = "\n\n".join(
            [f"[{c.doc_id} — {c.metadata.get('section_title', '')}]\n{c.content}" for c, _ in retrieved_items]
        )

        # 2. Sinh câu trả lời bằng LLM
        system_content = rag_template.replace("{context}", context_text).replace("{question}", sample.question)
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": sample.question},
        ]

        answer, usage = llm.chat(messages, temperature=0.0)

        # 3. Tính toán các chỉ số
        hit_rate = calculate_hit_rate(retrieved_docs, sample.expected_doc_ids)
        faithfulness = evaluate_faithfulness(llm, answer, context_text)
        relevance = evaluate_relevance(llm, sample.question, answer)

        is_no_ans = "không tìm thấy thông tin" in answer.lower()

        records.append({
            "sample_id": sample.id,
            "category": sample.category,
            "question": sample.question,
            "config": mode,
            "retrieved_docs": ", ".join(retrieved_docs),
            "hit_rate": hit_rate,
            "faithfulness": faithfulness,
            "relevance": relevance,
            "is_no_answer": is_no_ans,
            "latency_seconds": usage.latency_seconds,
            "total_tokens": usage.total_tokens,
            "generated_answer": answer,
        })

        # Nghỉ nhẹ 0.3s để đảm bảo không bị chạm giới hạn Rate Limit của API
        time.sleep(0.3)

    return records


def plot_comparison_chart(df: pd.DataFrame, output_path: str | Path):
    """
    Vẽ biểu đồ cột trực quan hóa so sánh chất lượng giữa 2 cấu hình Dense và Hybrid.
    """
    summary = df.groupby("config")[["hit_rate", "faithfulness", "relevance"]].mean().reset_index()

    configs = summary["config"].tolist()
    metrics = ["Retrieval Hit Rate", "Faithfulness (Không ảo giác)", "Answer Relevance"]

    x = range(len(metrics))
    width = 0.35

    fig, ax = plt.subplots(figsize=(9, 5.5))

    # Lấy dữ liệu của từng cấu hình
    dense_vals = [
        summary.loc[summary["config"] == "dense", m].values[0]
        for m in ["hit_rate", "faithfulness", "relevance"]
    ] if "dense" in configs else [0, 0, 0]

    hybrid_vals = [
        summary.loc[summary["config"] == "hybrid", m].values[0]
        for m in ["hit_rate", "faithfulness", "relevance"]
    ] if "hybrid" in configs else [0, 0, 0]

    rects1 = ax.bar([i - width/2 for i in x], dense_vals, width, label="Dense (Vector thuần)", color="#4A90E2")
    rects2 = ax.bar([i + width/2 for i in x], hybrid_vals, width, label="Hybrid (BM25 + Vector)", color="#50E3C2")

    ax.set_ylabel("Điểm số trung bình (0.0 - 1.0)", fontsize=11)
    ax.set_title("So sánh Hiệu năng RAG: Dense Retrieval vs Hybrid Retrieval", fontsize=13, fontweight="bold")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_ylim(0, 1.15)
    ax.legend(loc="upper right", fontsize=10)
    ax.grid(axis="y", linestyle="--", alpha=0.5)

    # Gắn nhãn số liệu lên đầu cột
    for rect in rects1 + rects2:
        height = rect.get_height()
        ax.annotate(
            f"{height:.2f}",
            xy=(rect.get_x() + rect.get_width() / 2, height),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center", va="bottom", fontsize=10, fontweight="bold"
        )

    plt.tight_layout()
    plt.savefig(output_path, dpi=300)
    plt.close()
    print(f"Đã xuất biểu đồ so sánh thành công: {output_path}")


def main():
    testset_path = project_root / "tests" / "testset.jsonl"
    corpus_dir = project_root / "data" / "corpus"

    print("Đang khởi động hệ thống đánh giá RAG...")
    # Khởi tạo Chunker & Corpus
    chunker = PolicyChunker()
    chunks = chunker.chunk_corpus(corpus_dir)
    print(f"Đã nạp {len(chunks)} chunks từ kho quy chế.")

    # Khởi tạo Retriever & LLM
    retriever = HybridRetriever(chunks)
    llm = LLMClient()
    samples = load_testset(testset_path)
    print(f"Đã nạp {len(samples)} câu hỏi kiểm thử từ testset.jsonl.")

    # 1. Chạy cấu hình 1: Dense Retrieval
    dense_records = evaluate_configuration(samples, retriever, llm, mode="dense", top_k=3)

    # 2. Chạy cấu hình 2: Hybrid Retrieval
    hybrid_records = evaluate_configuration(samples, retriever, llm, mode="hybrid", top_k=3)

    # Tổng hợp vào DataFrame
    all_records = dense_records + hybrid_records
    df = pd.DataFrame(all_records)

    # 3. Xuất file CSV chi tiết
    csv_path = project_root / "eval_results.csv"
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    print(f"\nĐã xuất bảng kết quả chi tiết: {csv_path}")

    # 4. Xuất biểu đồ đồ họa so sánh
    chart_path = project_root / "eval_comparison.png"
    plot_comparison_chart(df, chart_path)

    # 5. In bảng tổng kết hiệu năng ra màn hình
    print("\n" + "="*65)
    print("BẢNG TỔNG KẾT ĐÁNH GIÁ 2 CẤU HÌNH (RAG EVALUATION SUMMARY)")
    print("="*65)
    summary = df.groupby("config").agg({
        "hit_rate": "mean",
        "faithfulness": "mean",
        "relevance": "mean",
        "latency_seconds": "mean",
        "total_tokens": "sum",
    }).reset_index()

    for _, row in summary.iterrows():
        print(f"Cấu hình: {row['config'].upper()}")
        print(f"  - Retrieval Hit Rate:  {row['hit_rate']*100:.1f}%")
        print(f"  - Faithfulness (Trung thực): {row['faithfulness']*100:.1f}%")
        print(f"  - Answer Relevance:    {row['relevance']*100:.1f}%")
        print(f"  - Độ trễ trung bình:   {row['latency_seconds']:.2f}s/câu")
        print(f"  - Tổng token tiêu thụ: {int(row['total_tokens'])} tokens")
        print("-" * 65)

    print("\nHoàn thành toàn bộ quy trình đánh giá!")


if __name__ == "__main__":
    main()