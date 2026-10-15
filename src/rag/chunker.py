"""
Module: src.rag.chunker
Mô tả: Phân đoạn văn bản quy chế chi tiêu công tác theo cấu trúc ngữ nghĩa (Section-based Recursive Chunking).

Chiến lược Chunking & Biện minh thiết kế (Design Justification):
1. Tính nguyên vẹn ngữ nghĩa: Quy chế chi tiêu của doanh nghiệp được cấu trúc chặt chẽ theo từng 'Điều' hoặc 'Mục'.
   Việc cắt cố định theo số ký tự (Fixed-size chunking) có rủi ro nghiêm trọng là cắt ngang mệnh đề quy định
   (ví dụ: tách rời số tiền định mức $50 khỏi điều kiện áp dụng), gây ra hiện tượng ảo giác (hallucination) cho LLM.
2. Kích thước Chunk (400 - 800 ký tự): Khớp với độ dài trung bình của 1 Điều khoản quy chế, vừa vặn đưa vào Context Window
   của LLM mà không làm loãng thông tin (Information Dilution).
3. Overlap (100 ký tự): Khi một điều khoản quá dài cần tách đoạn đệ quy, overlap 100 ký tự bảo toàn ngữ cảnh liên kết.
4. Bảo toàn Metadata: Mỗi chunk được đính kèm toàn bộ Metadata gốc (doc_id, title, year, status) và tên điều khoản,
   đảm bảo khả năng trích dẫn nguồn chính xác (Citation Accuracy) và phục vụ bộ lọc Metadata Filter.
"""

import re
from pathlib import Path
from typing import Optional
from src.models.document import Document, DocumentChunk, DocumentMetadata


def parse_frontmatter(file_content: str) -> tuple[DocumentMetadata, str]:
    """
    Trích xuất phần YAML Frontmatter ở đầu file văn bản (nằm giữa cặp dấu ---).
    Trả về tuple: (đối tượng DocumentMetadata, nội dung văn bản còn lại).
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
    match = re.search(pattern, file_content, flags=re.DOTALL)
    
    if not match:
        # Trường hợp văn bản không có header YAML, tạo metadata mặc định
        metadata = DocumentMetadata(
            doc_id="DOC_UNKNOWN",
            title="Tài liệu không tên",
        )
        return metadata, file_content.strip()

    frontmatter_raw = match.group(1)
    body_text = match.group(2).strip()

    # Phân tích các cặp key: value trong frontmatter
    meta_dict = {}
    for line in frontmatter_raw.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            meta_dict[key.strip()] = val.strip()

    metadata = DocumentMetadata(
        doc_id=meta_dict.get("doc_id", "DOC_UNKNOWN"),
        title=meta_dict.get("title", "Chính sách chưa đặt tên"),
        category=meta_dict.get("category", "travel_policy"),
        version=meta_dict.get("version", "1.0"),
        effective_date=meta_dict.get("effective_date", "2024-01-01"),
        owner=meta_dict.get("owner", "Finance Department"),
        status=meta_dict.get("status", "active"),
    )
    return metadata, body_text


def split_into_sections(text: str) -> list[tuple[str, str]]:
    """
    Chia nhỏ văn bản thành các mục dựa trên tiêu đề Markdown (## Điều..., ## Mục..., ###...).
    Trả về danh sách tuple: [(tiêu_đề_mục, nội_dung_mục)].
    """
    # Regex tìm các tiêu đề cấp 2 hoặc 3: ## Điều 1: ..., ## Mục 2: ...
    header_pattern = r"(?m)^(#{2,3}\s+.+)$"
    parts = re.split(header_pattern, text)

    sections: list[tuple[str, str]] = []
    
    # Phần giới thiệu đầu tiên trước khi vào Điều 1 (nếu có)
    if parts[0].strip():
        sections.append(("Phần mở đầu", parts[0].strip()))

    # Các cặp: parts[i] là header, parts[i+1] là nội dung
    for i in range(1, len(parts), 2):
        header_title = parts[i].strip().lstrip("#").strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        if content:
            sections.append((header_title, content))

    return sections


def recursive_split_text(text: str, max_chunk_size: int = 800, overlap: int = 100) -> list[str]:
    """
    Nếu một Điều khoản quá dài (> max_chunk_size), chia nhỏ đệ quy theo đoạn văn (\n\n) hoặc câu (. )
    với khoảng đè lặp (overlap) để không làm mất mạch ý.
    """
    if len(text) <= max_chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + max_chunk_size
        if end >= text_len:
            chunks.append(text[start:].strip())
            break

        # Tìm điểm ngắt tự nhiên gần nhất (xuống dòng hoặc dấu chấm) để không cắt cụt từ
        split_idx = text.rfind("\n\n", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = text.rfind(". ", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = text.rfind(" ", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = end

        chunk_str = text[start:split_idx].strip()
        if chunk_str:
            chunks.append(chunk_str)

        start = max(split_idx - overlap, start + 1)

    return chunks


class PolicyChunker:
    """
    Lớp xử lý cắt tài liệu quy chế thành các DocumentChunk hoàn chỉnh.
    """

    def __init__(self, max_chunk_size: int = 800, overlap: int = 100):
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    def chunk_document(self, doc: Document) -> list[DocumentChunk]:
        """Chia nhỏ một tài liệu Document thành danh sách DocumentChunk."""
        sections = split_into_sections(doc.content)
        chunks: list[DocumentChunk] = []
        chunk_idx = 1

        for section_title, section_content in sections:
            # Chia nhỏ nếu đoạn văn dài hơn max_chunk_size
            sub_chunks = recursive_split_text(
                section_content,
                max_chunk_size=self.max_chunk_size,
                overlap=self.overlap,
            )

            for text_part in sub_chunks:
                chunk_id = f"{doc.doc_id}_c{chunk_idx:03d}"
                
                # Tạo chunk metadata kế thừa từ tài liệu gốc + vị trí điều khoản
                chunk_meta = {
                    "doc_id": doc.doc_id,
                    "title": doc.title,
                    "section_title": section_title,
                    "year": doc.metadata.year,
                    "status": doc.metadata.status,
                    "effective_date": doc.metadata.effective_date,
                    "version": doc.metadata.version,
                    "category": doc.metadata.category,
                }

                # Thêm tiền tố định danh vào nội dung chunk giúp LLM hiểu chính xác nguồn gốc
                augmented_content = (
                    f"[{doc.title} — {section_title} (Hiệu lực: {doc.metadata.effective_date})]\n"
                    f"{text_part}"
                )

                chunk = DocumentChunk(
                    chunk_id=chunk_id,
                    doc_id=doc.doc_id,
                    content=augmented_content,
                    chunk_index=chunk_idx,
                    metadata=chunk_meta,
                )
                chunks.append(chunk)
                chunk_idx += 1

        return chunks

    def chunk_file(self, file_path: Path | str) -> list[DocumentChunk]:
        """Đọc file từ ổ đĩa và trả về danh sách DocumentChunk."""
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")
        metadata, body = parse_frontmatter(content)
        
        doc = Document(
            doc_id=metadata.doc_id,
            title=metadata.title,
            content=body,
            metadata=metadata,
            source=str(path),
        )
        return self.chunk_document(doc)

    def chunk_corpus(self, corpus_dir: Path | str) -> list[DocumentChunk]:
        """Duyệt toàn bộ thư mục data/corpus/ để cắt tất cả văn bản."""
        dir_path = Path(corpus_dir)
        all_chunks: list[DocumentChunk] = []

        for file_path in sorted(dir_path.glob("DOC*.txt")):
            file_chunks = self.chunk_file(file_path)
            all_chunks.extend(file_chunks)

        return all_chunks