"""
1. Hai chế độ truy vấn: Dense Retrieval (Vector) và Hybrid Retrieval (BM25 + Vector).
2. Chuẩn hóa điểm Min-Max Scaling (normalize_scores) để dung hợp hai thang điểm khác biệt.
3. Weighted Fusion: 0.3 BM25 + 0.7 Vector.
4. Metadata Filtering để loại bỏ văn bản cũ hết hiệu lực.
"""

from typing import Optional, Any
from src.models.document import DocumentChunk
from src.rag.bm25_search import BM25SearchEngine, tokenize_vietnamese
from src.rag.vector_store import VectorStore, cosine_similarity, embed_text


def normalize_scores(scores: list[float]) -> list[float]:
    """
    Chuẩn hóa danh sách điểm số về khoảng [0.0, 1.0] bằng Min-Max Scaling.
    Ngăn chặn việc thang điểm lớn của BM25 lấn át thang điểm [-1, 1] của Cosine.
    """
    if not scores:
        return []
    min_s = min(scores)
    max_s = max(scores)
    if max_s == min_s:
        # Nếu tất cả các điểm bằng nhau, gán đồng đều là 1.0 (hoặc 0.0 nếu đều là 0)
        return [1.0 if max_s > 0 else 0.0] * len(scores)
    return [(s - min_s) / (max_s - min_s) for s in scores]


class HybridRetriever:
    """
    Bộ truy xuất tài liệu quy chế hỗ trợ cả Dense Search, BM25 và Hybrid Search.
    """

    def __init__(
        self,
        chunks: list[DocumentChunk],
        w_bm25: float = 0.3,
        w_vector: float = 0.7,
    ):
        """
        Khởi tạo với danh sách DocumentChunk và trọng số dung hợp (mặc định 0.3 BM25 / 0.7 Vector).
        """
        self.chunks = chunks
        self.w_bm25 = w_bm25
        self.w_vector = w_vector

        # Khởi tạo 2 công cụ tìm kiếm thành phần
        self.bm25_engine = BM25SearchEngine(self.chunks)
        self.vector_store = VectorStore(self.chunks)

    def filter_chunks(
        self,
        chunks: list[DocumentChunk],
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[DocumentChunk]:
        """
        Lọc danh sách chunk theo metadata.
        """
        if not metadata_filter:
            return chunks

        filtered = []
        for chunk in chunks:
            match = True
            for key, expected_val in metadata_filter.items():
                # So sánh với metadata của từng chunk
                chunk_val = chunk.metadata.get(key)
                if chunk_val != expected_val:
                    match = False
                    break
            if match:
                filtered.append(chunk)

        return filtered

    def retrieve_dense(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Chế độ truy vấn 1: Dense Retrieval (Vector Search).
        """
        candidates = self.filter_chunks(self.chunks, metadata_filter)
        if not candidates:
            return []

        query_vec = embed_text(query)
        scored = []
        for chunk in candidates:
            if chunk.embedding is not None:
                score = cosine_similarity(query_vec, chunk.embedding)
                scored.append((chunk, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def retrieve_hybrid(
        self,
        query: str,
        top_k: int = 5,
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Chế độ truy vấn 2: Hybrid Retrieval.
        Kết hợp BM25 + Vector thông qua Min-Max Normalization và Weighted Sum.
        """
        # Bước 1: Áp dụng Metadata Filter để thu hẹp không gian tìm kiếm (từ w4/ex3_1)
        candidates = self.filter_chunks(self.chunks, metadata_filter)
        if not candidates:
            return []

        # Bước 2: Tính điểm BM25 cho các candidate
        tokenized_query = tokenize_vietnamese(query)
        # Sử dụng chỉ mục BM25 của tập candidate
        candidate_corpus = [
            tokenize_vietnamese(c.content) for c in candidates
        ]
        from rank_bm25 import BM25Okapi
        bm25_cand = BM25Okapi(candidate_corpus)
        raw_bm25_scores = list(bm25_cand.get_scores(tokenized_query))

        # Bước 3: Tính điểm Vector (Cosine Similarity) cho các candidate
        query_vec = embed_text(query)
        raw_vec_scores = [
            cosine_similarity(query_vec, c.embedding) if c.embedding is not None else 0.0
            for c in candidates
        ]

        # Bước 4: Chuẩn hóa Min-Max Scaling cả 2 thang điểm về [0, 1] (Bắt buộc theo w4)
        norm_bm25 = normalize_scores(raw_bm25_scores)
        norm_vec = normalize_scores(raw_vec_scores)

        # Bước 5: Dung hợp điểm số theo trọng số: 0.3 * BM25 + 0.7 * Vector
        hybrid_results: list[tuple[DocumentChunk, float]] = []
        for i, chunk in enumerate(candidates):
            fused_score = (self.w_bm25 * norm_bm25[i]) + (self.w_vector * norm_vec[i])
            hybrid_results.append((chunk, fused_score))

        # Bước 6: Sắp xếp giảm dần và lấy top_k
        hybrid_results.sort(key=lambda x: x[1], reverse=True)
        return hybrid_results[:top_k]

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        metadata_filter: Optional[dict[str, Any]] = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """
        Cổng giao tiếp thống nhất hỗ trợ chọn chế độ ('dense' hoặc 'hybrid').
        Dùng để chạy đánh giá so sánh 2 cấu hình.
        """
        if mode == "dense":
            return self.retrieve_dense(query, top_k=top_k, metadata_filter=metadata_filter)
        elif mode == "hybrid":
            return self.retrieve_hybrid(query, top_k=top_k, metadata_filter=metadata_filter)
        else:
            raise ValueError(f"Chế độ truy vấn không hợp lệ: {mode}. Chỉ hỗ trợ 'dense' hoặc 'hybrid'.")