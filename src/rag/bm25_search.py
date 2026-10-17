import re
from rank_bm25 import BM25Okapi
from src.models.document import DocumentChunk

def tokenize_vietnamese(text: str) -> list[str]:
    """
    tiền xử lý và tách từ khoá cơ bản cho tiếng việt:
    chuyển tonaf bộ về chữ thường (lowercase)
    dùng regular expression để giữ lại từ ngữ, các con số và ký hiệu tiền tệ quan trọng
    """ 
    clean_text = text.lower()
    # \w+ lấy các từ chữ và số, [\$]\d+ giữ lại định dạng tiền tệ như 50$, 60$
    tokens = re.findall(f"[\$]?\w+", clean_text, flags=re.UNICODE)
    return tokens

class BM25SearchEngine:
    """
    Lớp tìm kiếm BM25 cho các DocumentChunk.
    """
    def __init__(self, chunks: list[DocumentChunk]):
        self.chunks = chunks
        #tách từ hco toàn bộ chunks trong kho
        self.tokenized_corpus = [
            tokenize_vietnamese(chunk.content) for chunk in self.chunks
        ]
        #xây dựng mô hình BM25
        self.bm25 = BM25Okapi(self.tokenized_corpus)

    def search(self, query: str, top_k: int = 5) -> list[tuple[DocumentChunk, float]]:
        """
        tìm kiến các chunk có độ khớp từ khoá cao nhất với câu hỏi.
        tham số:
            query: câu hỏi truy vấn của người dùng (ví dụ: "hạn mức ăn uống mỗi ngày là bao nhiêu?")
            top_k: số lượng chunk tối đa cần trả về (mặc định là 5)
        trả về:
            danh sách các cặp (DocumentChunk, điểm_BM25) được sắp xếp giảm dần theo điểm số
        """
        tokenized_query = tokenize_vietnamese(query)
        if not tokenized_query:
            return []

        #tính toán điểm BM25 cho câu truy vấn đối với từng chunk trong kho
        scores = self.bm25.get_scores(tokenized_query)

        #ghép cặp từng chunk với điểm số tương ứng
        scored_chunks: list[tuple[DocumentChunk, float]] = []
        for chunk, score in zip(self.chunks, scores):
            #chủ giữ lại các chunk thực sự có chứa từ khoá (điểm > 0)
            if score > 0.0:
                scored_chunks.append((chunk, float(score)))

        #sắp xếp giảm dần theo điểm BM25 (điểm càng cao càng khớp từ khoá)
        scored_chunks.sort(key=lambda item: item[1], reverse=True)

        return scored_chunks[:top_k]