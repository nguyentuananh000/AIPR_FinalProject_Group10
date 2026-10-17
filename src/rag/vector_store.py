"""
bộ lưu trữ vector và tìm kiếm ngữ nghĩa (dense retrieval) sử dụng cosine similarity

- tìm kiếm ngữ nghĩa (semantic search): khác với BM25 tìm từ khoá trùng hợp, vector search chuyển hoá câu hỏi và văn bản thành các
vector số học đa chiều để tìm kiếm ý nghĩa trừu tượng 
"""

import os 
import json
from pathlib import Path
from typing import Optional
import numpy as np
import requests
from dotenv import load_dotenv

from src.models.document import DocumentChunk

load_dotenv()


def cosine_similarity(v1: list[float] | np.ndarray, v2: list[float] | np.ndarray) -> float:
    """
    tính độ tương đồng cosine giữa 2 vector
    Cosine(u, v) = (u . v) / (||u|| * ||v||)
    Trả về giá trị trong khoảng [-1.0, 1.0], càng gần 1.0 càng đồng nghĩa.
    """
    a= np.array(v1, dtype=float)
    b= np.array(v2, dtype=float)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))

def _fallback_embedding(text: str, dim: int = 1024) -> list[float]:
    """
    hàm tạo vector giả lập dự phòng
    """
    #lấy sễ từ tổng giá trị kí tự để đảm bảo cùng 1 câu sẽ sinh ra cùng 1 vector
    seed = abs(hash(text)) % (2**32)
    rng = np.random.RandomState(seed)
    vec = rng.randn(dim)
    norm = np.linalg.norm(vec)
    return (vec / (norm if norm > 0 else 1.0)).tolist()

def embed_text(text: str) -> list[float]:
    """
    tạo vector embedding cho 1 đoạn văn bản
    """
    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent?key={gemini_key}"
            payload = {
                "model": "models/gemini-embedding-001",
                "content": {"parts": [{"text": text}]},
            }
            res = requests.post(url, json=payload, timeout=10)
            if res.status_code == 200:
                return res.json()["embedding"]["values"]
        except Exception:
            pass
    jina_key = os.getenv("JINA_API_KEY")
    if jina_key:
        try:
            url = "https://api.jina.ai/v1/embeddings"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {jina_key}",
            }
            data = {
                "model": "jina-embeddings-v3",
                "task": "retrieval.passage",
                "input": [text],
            }
            res = requests.post(url, headers=headers, json=data, timeout=10)
            if res.status_code == 200:
                return res.json()["data"][0]["embedding"]
        except Exception:
            pass
    return _fallback_embedding(text)

def batch_embed_text(texts: list[str]) -> list[list[float]]:
    """Tạo vector cho danh sách nhiều văn bản"""
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if gemini_key and texts:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={gemini_key}"
            payload = {
                "requests": [
                    {
                        "model": "models/gemini-embedding-001",
                        "content": {"parts": [{"text": t}]},
                    }
                    for t in texts
                ]
            }
            res = requests.post(url, json=payload, timeout=30)
            if res.status_code == 200:
                return [item["values"] for item in res.json()["embeddings"]]
        except Exception:
            pass
    return [_fallback_embedding(t) for t in texts]
class VectorStore:
    """
    Kho lưu trữ vector và thực thi tìm kiếm ngữ nghĩa (Dense Retrieval).
    """
    def __init__(self, chunks: Optional[list[DocumentChunk]] = None):
        self.chunks: list[DocumentChunk] = []
        if chunks:
            self.add_chunks(chunks)
    def add_chunks(self, chunks: list[DocumentChunk]) -> None:
        """Thêm các chunk vào kho và tính toán vector embedding nếu chưa có."""
        unembedded_texts = []
        unembedded_indices = []
        for idx, chunk in enumerate(chunks):
            self.chunks.append(chunk)
            if chunk.embedding is None:
                unembedded_texts.append(chunk.content)
                unembedded_indices.append(len(self.chunks) - 1)
        # Batch embedding cho các chunk mới để tiết kiệm thời gian
        if unembedded_texts:
            embeddings = batch_embed_text(unembedded_texts)
            for chunk_idx, emb in zip(unembedded_indices, embeddings):
                self.chunks[chunk_idx].embedding = emb
    def search(self, query: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        """
        Tìm kiếm các chunk có độ tương đồng ngữ nghĩa cao nhất bằng Cosine Similarity.
        
        Trả về:
            Danh sách tuple: (DocumentChunk, điểm_cosine) giảm dần theo điểm số.
        """
        if not self.chunks:
            return []
        query_vec = embed_text(query)
        scored_chunks: list[tuple[DocumentChunk, float]] = []
        for chunk in self.chunks:
            if chunk.embedding is None:
                continue
            score = cosine_similarity(query_vec, chunk.embedding)
            scored_chunks.append((chunk, score))
        # Sắp xếp giảm dần theo điểm Cosine
        scored_chunks.sort(key=lambda item: item[1], reverse=True)
        return scored_chunks[:top_k]
    def save(self, filepath: str | Path) -> None:
        """Lưu toàn bộ chunk kèm vector ra file JSON để tái sử dụng nhanh."""
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [chunk.to_dict() for chunk in self.chunks]
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    def load(self, filepath: str | Path) -> None:
        """Đọc lại dữ liệu chunk và vector đã lưu từ JSON."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Không tìm thấy file vector: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        self.chunks = []
        for item in data:
            chunk = DocumentChunk(
                chunk_id=item["chunk_id"],
                doc_id=item["doc_id"],
                content=item["content"],
                chunk_index=item["chunk_index"],
                metadata=item.get("metadata", {}),
                embedding=item.get("embedding"),
            )
            self.chunks.append(chunk)