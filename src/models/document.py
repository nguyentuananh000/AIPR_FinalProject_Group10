from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional

@dataclass
class DocumentMetadata:
    """Luu trữ thông tin quản lý (metadata) của một văn bản quy chế"""
    doc_id: str
    title: str
    category: str = "travel_policy"
    version: str = "1.0"
    effective_date: str = "2024-01-01"
    owner: str = "HR & Finance"
    status: str = "active"

    @property
    def year(self) -> int:
        """Trích xuất năm hiệu lực (ví dụ '2024-01-01' -> 2024) để phục vụ metadata filter."""
        return int(self.effective_date.split("-")[0])

@dataclass
class DocumentChunk:
    """Đại diện cho một mảnh văn bản (chunk) sau khi cắt nhỏ từ tài liệu gốc."""
    chunk_id: str
    doc_id: str
    content: str
    chunk_index: int
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: Optional[list[float]] = None
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        """chuyển đối tượng thành dictionary để lưu ra file json"""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()    
        return data

@dataclass
class Document:
    """Đại diện cho một văn bản quy chế hoàn chỉnh trước khi chia chunk"""
    doc_id: str
    title: str
    content: str
    metadata: DocumentMetadata
    source: str = ""