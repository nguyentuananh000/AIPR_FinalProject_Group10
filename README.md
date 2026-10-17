# AIPR Final Project — Group 10
## Đề tài T2: Kiểm toán chi tiêu công tác (Agent Kiểm toán & Đối soát Chi phí Công tác)

**Môn học:** Lập trình AI với Python (AIPR) — Học kỳ 1, Năm học 2026-2027  
**Nhóm:** 10  
- **Thành viên A:** Nguyễn Tuấn Anh (RAG Engine, Data & Evaluation)
- **Thành viên B:** Lâm Quốc Trung (ReAct Agent, MCP Server & Tool)

---


## 🚀 HƯỚNG DẪN KHỞI CHẠY BẰNG 1 LỆNH (COLD-START)

### Bước 1: Cài đặt môi trường
Khuyến nghị sử dụng Python 3.10+:
```bash
pip install -r requirements.txt
```

### Bước 2: Cấu hình biến môi trường
Sao chép tệp mẫu `.env.example` thành `.env` và điền các API Key:
```bash
cp .env.example .env
```
Các khóa tối thiểu:
- `GROQ_API_KEY`: Lấy miễn phí tại [console.groq.com/keys](https://console.groq.com/keys)
- `GEMINI_API_KEY`: Lấy miễn phí tại [aistudio.google.com/apikey](https://aistudio.google.com/apikey)

### Bước 3: Chạy hệ thống bằng 1 lệnh duy nhất
```bash
# Khởi chạy giao diện tương tác Menu dòng lệnh:
python main.py

# Hoặc tra cứu nhanh quy chế công tác phí bằng RAG:
python main.py --query "Hạn mức tiền ăn mỗi ngày là bao nhiêu?"

# Hoặc kiểm toán ngay một mã hồ sơ chi phí cụ thể:
python main.py --claim CLM-101

# Hoặc chạy đánh giá tự động toàn diện:
python main.py --eval
```

---

## 📊 THỰC NGHIỆM ĐÁNH GIÁ (BENCHMARK EVALUATION)

Hệ thống được kiểm thử tự động trên bộ dữ liệu chuẩn 15 câu hỏi (`tests/testset.jsonl`), bao gồm 4 câu hỏi bẫy ảo giác (`no_answer`) theo chuẩn framework RAGAS (Tuần 5).

Chạy đánh giá và so sánh 2 cấu hình (Dense vs Hybrid) bằng lệnh:
```bash
python -m src.eval.run_eval
```

Kết quả sinh tự động:
- **`eval_results.csv`**: Bảng dữ liệu chi tiết từng câu kèm đo lường độ trễ (latency) và chi phí token (`UsageLog`).
- **`eval_comparison.png`**: Biểu đồ cột đồ họa so sánh trực quan giữa Dense Retrieval và Hybrid Retrieval.



