# BÁO CÁO KHAI BÁO SỬ DỤNG TRỢ LÝ AI (AI USAGE REPORT)

- **Môn học:** Lập trình AI với Python (AIPR) — Học kỳ 1, Năm học 2026-2027
- **Đề tài:** T2 — Business Travel Expense Audit Agent
- **Nhóm học tập:** Nhóm 10
- **Thành viên:**
  1. Nguyễn Tuấn Anh (Thành viên A — RAG Engine, Data & Evaluation)
  2. [Họ và tên Thành viên B] (Thành viên B — ReAct Agent, MCP Server & Tool)
- **Repository:** https://github.com/nguyentuananh000/AIPR_FinalProject_Group10

---

## 1. CÔNG CỤ AI ĐÃ SỬ DỤNG
Trong suốt quá trình thực hiện đồ án, nhóm đã sử dụng các công cụ AI hỗ trợ lập trình sau:
1. **Google Antigravity / Gemini CLI** (Mô hình: Gemini 2.5 Flash / Claude 3.5 Sonnet).
2. **Groq API** (Mô hình: `openai/gpt-oss-20b` hoặc `llama-3.3-70b-versatile`) làm động cơ suy luận LLM cho ReAct Agent và LLM-as-a-Judge.
3. **Google Generative Language API** (Mô hình: `models/gemini-embedding-001`) để tạo vector biểu diễn ngữ nghĩa 3.072 chiều.

---

## 2. PHẠM VI SỬ DỤNG CHO TỪNG THÀNH VIÊN VÀ HẠNG MỤC

### A. Thành viên A — Nguyễn Tuấn Anh (RAG Engine, Data & Evaluation)
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

### B. Thành viên B (ReAct Agent & MCP Server)
* **MCP Server & Client:**
  - Dùng AI hỗ trợ khởi tạo khung MCP Server chạy qua giao thức `stdio` theo chuẩn SDK mới của Tuần 7.
  - Viết các Tool: `get_claim_details`, `submit_audit_decision`, `get_claim_status`.
  - Cấu hình chuyển toàn bộ nhật ký logging sang `sys.stderr` để giữ sạch luồng dữ liệu chuẩn `stdout`.
* **Vòng lặp ReAct Agent Loop & Safe Parser:**
  - Dùng AI tham khảo biểu thức chính quy (Regex) trong `parser.py` để trích xuất `Action: tool_name({...})` an toàn, chống crash khi LLM trả về thiếu dấu ngoặc.
  - Cài đặt cơ chế Side Effect + Verification: Sau khi gọi `submit_audit_decision`, agent tự động gọi `get_claim_status` để đối soát lại trạng thái lưu trữ trong cơ sở dữ liệu.

---

## 3. CÁC PROMPT CHÍNH ĐÃ SỬ DỤNG KHI TƯƠNG TÁC VỚI AI

### Prompt 1: Thiết kế bộ cắt văn bản theo Điều khoản (Chunking)
> *"Hãy hướng dẫn tôi viết một class PolicyChunker bằng Python bám sát cấu trúc các văn bản quy chế chi tiêu doanh nghiệp. Cần ưu tiên cắt theo từng Điều khoản (Markdown Header ## Điều...), độ dài mỗi chunk từ 400 đến 800 ký tự kèm 100 ký tự overlap nếu quá dài. Đính kèm metadata đầy đủ và viết 3-5 dòng docstring giải thích lý do thiết kế theo đúng Yêu cầu 2.5."*

### Prompt 2: Tái sử dụng Hybrid Search từ Tuần 4
> *"Trong bài lab tuần 4 môn học của tôi có file ex2_1_hybrid_search.py kết hợp BM25Okapi và Cosine Similarity bằng Min-Max Normalization và trọng số 0.3/0.7. Hãy giúp tôi tái cấu trúc thuật toán này thành class HybridRetriever kết hợp thêm bộ lọc Metadata Filter theo năm 2024 từ bài ex3_1 để lấy điểm thưởng đồ án."*

### Prompt 3: Thiết kế cơ chế Side-Effect + Verify cho Agent
> *"Hãy hướng dẫn tôi cách hiện thực hóa cơ chế Side Effect kèm Verify trong ReAct Agent loop theo yêu cầu 2.7. Khi agent gọi tool ghi dữ liệu `submit_audit_decision`, vòng lặp phải tự động gọi thêm tool đọc `get_claim_status` để xác minh xem trạng thái lưu trong cơ sở dữ liệu có khớp với quyết định vừa ghi hay không."*

---

## 4. PHẦN CODE DO AI HỖ TRỢ SINH RA VS. TỰ KIỂM SOÁT VÀ CHỈNH SỬA

| Mô đun | Tỷ lệ AI hỗ trợ sinh khung | Mức độ sinh viên can thiệp & làm chủ |
| :--- | :---: | :--- |
| **Kho quy chế (data/corpus/)** | 60% | Sinh viên tự thiết kế các bẫy logic ($50 vs $40, thời hạn 30 ngày, mất hóa đơn). |
| **Mô hình Dataclass** | 40% | Sinh viên tự định nghĩa các trường dữ liệu và phương thức `to_dict()`. |
| **RAG Pipeline (src/rag/)** | 50% | Sinh viên tự gõ tay, fix lỗi regex, điều chỉnh kích thước chunk, gỡ lỗi model Google embedding `gemini-embedding-001`. |
| **ReAct Loop & Parser** | 45% | Sinh viên tự cấu hình giới hạn `MAX_STEPS = 12`, xử lý chuỗi lỗi `"Error: ..."` an toàn. |
| **MCP Server & Client** | 40% | Sinh viên tự cấu hình giao thức `stdio`, đường dẫn cơ sở dữ liệu JSON và kiểm tra `list_tools()`. |
| **Framework Eval & Chart** | 50% | Sinh viên tự chạy thực nghiệm trên 15 câu testset, xử lý lỗi định dạng UTF-8 CSV và vẽ biểu đồ so sánh. |

---

## 5. CAM KẾT LIÊM CHÍNH HỌC THUẬT (ACADEMIC INTEGRITY PLEDGE)

1. Nhóm cam kết đã khai báo trung thực và minh bạch 100% việc sử dụng công cụ AI trong đồ án này theo đúng tinh thần và yêu cầu của môn học.
2. Không sao chép mã nguồn hay kho dữ liệu của bất kỳ nhóm sinh viên nào khác.
3. Cả hai thành viên đều **trực tiếp gõ mã nguồn, chạy thử nghiệm, thấu hiểu sâu sắc bản chất kỹ thuật của từng dòng lệnh** trong phần việc mình phụ trách và hoàn toàn sẵn sàng:
   - Trình bày kiến trúc hệ thống trực tiếp mà không cần phụ thuộc slide.
   - Trả lời độc lập các câu hỏi vấn đáp kỹ thuật chuyên sâu từ giảng viên.
   - Sửa đổi hoặc bổ sung code trực tiếp tại chỗ theo yêu cầu trong 20 phút bảo vệ cuối kỳ.
