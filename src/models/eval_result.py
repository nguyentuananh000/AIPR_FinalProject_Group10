from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Optional


@dataclass
class UsageLog:
    """Theo dõi chi phí token và độ trễ của từng câu hỏi (Yêu cầu log USAGE)"""
    calls: int = 1
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    max_prompt_tokens: int = 0
    latency_seconds: float = 0.0
    model: str = ""


@dataclass
class EvalSample:
    """Câu hỏi kiểm thử độc từ file test/testset.jsonl"""
    id: str
    question: str
    category: str
    reference_answer: str
    expected_doc_ids: list[str] = field(default_factory=list)
    expected_decision: Optional[str] = None


@dataclass
class EvalResult:
    """kết quả chấm điểm đánh giá cho 1 câu hỏi trong testset"""
    sample_id: str
    question: str
    category: str
    generated_answer: str
    retrieved_doc_ids: list[str] = field(default_factory=list)
    faithfulness_score: float = 0.0
    relevance_score: float = 0.0
    is_no_answer: bool = False
    usage: UsageLog = field(default_factory=UsageLog)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)