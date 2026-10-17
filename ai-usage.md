# BÁO CÁO KHAI BÁO SỬ DỤNG TRỢ LÝ AI (AI USAGE REPORT)

- **Môn học:** Lập trình AI với Python (AIPR) — Học kỳ 1, Năm học 2026-2027
- **Đề tài:** T2 — Kiểm toán chi tiêu công tác
- **Nhóm học tập:** Nhóm 10
- **Thành viên:**
  1. Nguyễn Tuấn Anh (RAG Engine, Data & Evaluation)
  2. Lâm Quốc Trung (ReAct Agent, MCP Server & Tool)
- **Repository:** https://github.com/nguyentuananh000/AIPR_FinalProject_Group10

---

## 1. CÔNG CỤ AI ĐÃ SỬ DỤNG
Trong suốt quá trình thực hiện đồ án, nhóm đã sử dụng các công cụ AI hỗ trợ lập trình sau:
1. **Google Antigravity / Gemini CLI**
2. **Groq API**
3. **Google Generative Language API** (Mô hình: `models/gemini-embedding-001`) để tạo vector biểu diễn ngữ nghĩa 3.072 chiều.
4. OpenAI Codex — hỗ trợ đọc hiểu cấu trúc dự án, giải thích luồng Agent/MCP, gỡ lỗi tích hợp Groq native tool call và xây dựng script chạy trace RAG một câu hỏi. Mã nguồn sau khi được hỗ trợ vẫn được thành viên kiểm tra và chạy trong môi trường dự án.
---

## 2. PHẠM VI SỬ DỤNG CHO TỪNG THÀNH VIÊN VÀ HẠNG MỤC

### A. Nguyễn Tuấn Anh (RAG Engine, Data & Evaluation)
* **Khởi tạo kho quy chế mẫu (DOC0001 - DOC0005):**
  - Dùng AI hỗ trợ soạn thảo 5 văn bản quy định chi tiêu công tác Acme Corp sát với thực tế doanh nghiệp và có gắn YAML Frontmatter chuẩn.
* **Mô hình dữ liệu Dataclass:**
  - Dùng AI gợi ý khung cấu trúc `@dataclass` cho `DocumentMetadata`, `DocumentChunk`, `UsageLog`, `EvalSample`, `EvalResult`.
* **RAG Pipeline (Chunking, BM25, VectorStore, Hybrid):**
  - Dùng AI tham khảo thuật toán `BM25Okapi` và kỹ thuật Feature Hashing (`_fallback_embedding`).
  - Tái sử dụng và chuẩn hóa công thức chuẩn hóa Min-Max Scaling kết hợp có trọng số $0.3 \times BM25 + 0.7 \times Vector$ từ bài lab Tuần 4.
  - Tích hợp bộ lọc Metadata Filter lọc theo năm 2024 và trạng thái active.
* **Hệ thống đánh giá RAGAS:**
  - Dùng AI hỗ trợ viết prompt phân tách Claim và prompt giám khảo LLM Judge (`judge_faithfulness.txt`, `judge_relevance.txt`).
  - Viết script `run_eval.py` tự động xuất `eval_results.csv` và vẽ biểu đồ cột `eval_comparison.png` bằng thư viện `matplotlib`.
* **Tạo ra các test case, chương trình test.**
  - 15 test cases, logs.
* **Các file được AI gen:**
  - data/corpus
  - generate_traces.py
  - logs/
  - llm_client.py
  - eval/
  - test/

### B. Lâm Quốc Trung (ReAct Agent & MCP Server)
* **MCP Server & Client:**
  - Dùng AI hỗ trợ khởi tạo khung MCP Server chạy qua giao thức `stdio` theo chuẩn SDK mới của Tuần 7.
  - Viết các Tool: `get_claim_details`, `submit_audit_decision`, `get_claim_status`.
  - Cấu hình chuyển toàn bộ nhật ký logging sang `sys.stderr` để giữ sạch luồng dữ liệu chuẩn `stdout`.
* **Vòng lặp ReAct Agent Loop & Safe Parser:**
  - Dùng AI tham khảo biểu thức chính quy (Regex) trong `parser.py` để trích xuất `Action: tool_name({...})` an toàn, chống crash khi LLM trả về thiếu dấu ngoặc.
  - Cài đặt cơ chế Side Effect + Verification: Sau khi gọi `submit_audit_decision`, agent tự động gọi `get_claim_status` để đối soát lại trạng thái lưu trữ trong cơ sở dữ liệu.
  - Mô hình dữ liệu nghiệp vụ: sử dụng AI để tham khảo cấu trúc ExpenseItem, ExpenseClaim và AuditDecision trong src/models/expense.py. Thành viên rà soát các trường dữ liệu và phương thức tính tổng chi phí theo hồ sơ.

  - Schema tham số MCP: tham khảo AI khi xây dựng các lớp tham số GetClaimDetailsParams, GetClaimStatusParams và SubmitAuditDecisionParams trong src/models/mcp_schema.py. MCP Server hiện công bố input schema thông qua chữ ký các hàm tool; các dataclass schema mô tả cấu trúc dữ liệu và chưa được dùng trực tiếp để tạo tham số gọi tool.

  - MCP Server và Client: dùng AI hỗ trợ tìm hiểu cách chạy server qua Stdio, đăng ký các tool đọc/ghi hồ sơ, giữ logging trên sys.stderr và khám phá danh sách tool cùng input schema bằng list_tools().

  - ReAct Agent và parser: tham khảo AI khi thiết kế vòng lặp giới hạn MAX_STEPS = 12, phân loại phản hồi thành action hoặc final answer, kiểm tra JSON arguments và chuyển lỗi tool thành Observation để agent xử lý tiếp.

  - Side Effect + Verify: xây dựng luồng tự động gọi get_claim_status sau khi submit_audit_decision ghi thành công, sau đó so sánh trạng thái đọc lại với trạng thái được yêu cầu.

  - Gỡ lỗi và trace: dùng Codex hỗ trợ xử lý lỗi Groq khi mô hình trả native tool call, điều chỉnh Client truyền tool schema đã khám phá vào lời gọi mô hình và ghi lại Action/Observation. Codex cũng hỗ trợ tạo script chạy một truy vấn RAG và lưu retrieval, token, độ trễ cùng câu trả lời vào trace log.
---

## 3. CÁC PROMPT CHÍNH ĐÃ SỬ DỤNG KHI TƯƠNG TÁC VỚI AI

### Prompt 1: Thiết kế bộ cắt văn bản theo Điều khoản (Chunking)
> *"Hãy hướng dẫn tôi viết một class PolicyChunker bằng Python bám sát cấu trúc các văn bản quy chế chi tiêu doanh nghiệp. Cần ưu tiên cắt theo từng Điều khoản (Markdown Header ## Điều...), độ dài mỗi chunk từ 400 đến 800 ký tự kèm 100 ký tự overlap nếu quá dài. Đính kèm metadata đầy đủ và viết 3-5 dòng docstring giải thích lý do thiết kế theo đúng Yêu cầu 2.5."*

### Prompt 2: Tái sử dụng Hybrid Search từ Tuần 4
> *"Trong bài lab tuần 4 môn học của tôi có file ex2_1_hybrid_search.py kết hợp BM25Okapi và Cosine Similarity bằng Min-Max Normalization và trọng số 0.3/0.7. Hãy giúp tôi tái cấu trúc thuật toán này thành class HybridRetriever kết hợp thêm bộ lọc Metadata Filter theo năm 2024 từ bài ex3_1 để lấy điểm thưởng đồ án."*

### Prompt 3: Thiết kế cơ chế Side-Effect + Verify cho Agent
> *"Hãy hướng dẫn tôi cách hiện thực hóa cơ chế Side Effect kèm Verify trong ReAct Agent loop theo yêu cầu 2.7. Khi agent gọi tool ghi dữ liệu `submit_audit_decision`, vòng lặp phải tự động gọi thêm tool đọc `get_claim_status` để xác minh xem trạng thái lưu trong cơ sở dữ liệu có khớp với quyết định vừa ghi hay không."*

### Prompt 4: Thiết kế dataclass cho dữ liệu kiểm toán

“Hãy giải thích và đề xuất cấu trúc dataclass Python cho ExpenseItem, ExpenseClaim và AuditDecision của hệ thống kiểm toán chi phí công tác. Nêu vai trò từng trường, cách khởi tạo danh sách chi phí an toàn bằng default_factory và cách tính tổng số tiền yêu cầu.”

### Prompt 5: Xây dựng MCP Server và Client

“Hãy hướng dẫn xây dựng MCP Server Python qua Stdio với ba tool get_claim_details, submit_audit_decision và get_claim_status. Server đọc và cập nhật database JSON, kiểm tra mã hồ sơ/trạng thái, trả lỗi dạng chuỗi và ghi log ra stderr. Hướng dẫn Client khám phá tools cùng input schema bằng list_tools() thay vì khai báo cứng.”

### Prompt 6: Gỡ lỗi ReAct Agent và xác minh thao tác ghi

“Hãy rà soát vòng lặp ReAct tích hợp MCP. Agent cần giới hạn số bước, xử lý phản hồi sai định dạng và lỗi tool an toàn. Sau khi submit_audit_decision thành công, tự gọi get_claim_status để đọc lại trạng thái. Phân tích trace để phân biệt lời gọi tool, Observation và câu trả lời cuối.”

