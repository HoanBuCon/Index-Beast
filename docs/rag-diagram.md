# Sơ đồ RAG của IndexBeast

**Nhóm:** 4 Hollows  
**Phạm vi:** lore Elden Ring base game  
**Luồng mô tả:** xử lý câu hỏi trên kho tri thức đã được đánh chỉ mục

Sơ đồ tập trung vào quá trình truy xuất và sinh câu trả lời. Qdrant đã có sẵn
vector, nội dung các đoạn văn và metadata nguồn. Đây là thiết kế dự kiến của
pipeline RAG; API thử DeepSeek hiện tại mới gọi model trực tiếp.

```mermaid
flowchart TD
    START["Người dùng đặt câu hỏi trên Web hoặc Discord"]
    API["FastAPI nhận và kiểm tra request"]
    HISTORY["Lấy lịch sử hội thoại liên quan"]
    PG[("PostgreSQL: hội thoại và trace")]
    REWRITE["DeepSeek viết lại câu hỏi thành truy vấn độc lập"]
    SCOPE{"Câu hỏi thuộc phạm vi lore base game"}
    OUT["Thông báo ngoài phạm vi"]
    QUERY["Truy vấn tiếng Anh, tên thực thể và bộ lọc metadata"]

    START --> API
    API --> HISTORY
    PG -.->|"Lịch sử"| HISTORY
    HISTORY --> REWRITE
    REWRITE --> SCOPE
    SCOPE -->|"Không"| OUT
    SCOPE -->|"Có"| QUERY

    E5["E5 tạo dense embedding cho truy vấn"]
    DENSE["Dense search theo ngữ nghĩa"]
    BM25["BM25 search theo từ khóa"]
    QDRANT[("Qdrant: kho chunk đã đánh chỉ mục")]
    FUSION["RRF hợp nhất thứ hạng hai danh sách kết quả"]
    RERANK["Reranker chấm lại độ liên quan của từng chunk"]
    ENOUGH{"Có đủ bằng chứng liên quan"}

    QUERY --> E5
    E5 --> DENSE
    QUERY --> BM25
    QDRANT -.->|"Dense vector và payload"| DENSE
    QDRANT -.->|"Sparse vector và payload"| BM25
    DENSE --> FUSION
    BM25 --> FUSION
    FUSION --> RERANK
    RERANK --> ENOUGH

    WEB_ENABLED{"Bật web fallback"}
    WEB["Tìm nguồn web thuộc phạm vi base game"]
    WEB_RERANK["Rerank ngữ cảnh bổ sung một lượt"]
    WEB_ENOUGH{"Ngữ cảnh bổ sung đủ liên quan"}
    REFUSE["Thông báo chưa tìm được đủ thông tin"]
    CONTEXT["Chọn top K chunk và đánh số nguồn"]

    ENOUGH -->|"Có"| CONTEXT
    ENOUGH -->|"Không"| WEB_ENABLED
    WEB_ENABLED -->|"Không"| REFUSE
    WEB_ENABLED -->|"Có"| WEB
    WEB --> WEB_RERANK
    WEB_RERANK --> WEB_ENOUGH
    WEB_ENOUGH -->|"Có"| CONTEXT
    WEB_ENOUGH -->|"Không hoặc lỗi"| REFUSE

    PROMPT["Ghép system prompt, câu hỏi gốc và các đoạn nguồn"]
    GENERATE["DeepSeek sinh câu trả lời dựa trên ngữ cảnh"]
    CITATIONS["Ánh xạ trích dẫn với tiêu đề, section và URL"]
    ANSWER["Trả câu trả lời và nguồn về Web hoặc Discord"]
    TRACE["Lưu hội thoại, nguồn, token và độ trễ"]
    END["Kết thúc lượt hỏi đáp"]

    CONTEXT --> PROMPT
    PROMPT --> GENERATE
    GENERATE --> CITATIONS
    CITATIONS --> ANSWER
    CITATIONS --> TRACE
    TRACE --> PG
    ANSWER --> END
    OUT --> END
    REFUSE --> END

    classDef storage fill:#e8f3ed,stroke:#4c8066,color:#173d2c;
    classDef model fill:#eaf1fb,stroke:#557da8,color:#19324f;
    classDef optional fill:#fff3da,stroke:#af873d,color:#55401c;
    classDef output fill:#f0eafb,stroke:#8468a8,color:#39264e;
    class QDRANT,PG storage;
    class REWRITE,E5,RERANK,GENERATE model;
    class WEB_ENABLED,WEB,WEB_RERANK,WEB_ENOUGH optional;
    class ANSWER,REFUSE,OUT output;
```

## Giải thích luồng xử lý

1. **Nhận câu hỏi:** Web và Discord dùng chung API. Backend lấy lịch sử cần thiết
   để hiểu các câu hỏi tiếp nối.
2. **Viết lại truy vấn:** DeepSeek chuyển câu hỏi thành truy vấn độc lập, xác định
   thực thể và ngôn ngữ. Tên riêng trong game được giữ để hỗ trợ tìm kiếm.
3. **Hybrid retrieval:** tìm kiếm ngữ nghĩa bằng embedding E5 và tìm kiếm từ khóa
   bằng BM25 trên Qdrant. Bộ lọc giới hạn nội dung ở `game_scope=base`.
4. **Hợp nhất và rerank:** RRF hợp nhất thứ hạng, sau đó reranker chọn các đoạn
   phù hợp hơn để đưa vào ngữ cảnh.
5. **Xử lý thiếu bằng chứng:** thử web fallback nếu được bật. Nhánh này chạy trong
   lúc trả lời và không tạo dataset mới. Nếu vẫn thiếu thông tin thì thông báo rõ.
6. **Sinh câu trả lời:** DeepSeek nhận câu hỏi gốc và các đoạn nguồn có đánh số.
   Câu trả lời giữ ngôn ngữ người hỏi và gắn trích dẫn về nguồn tương ứng.
7. **Trả kết quả và lưu trace:** hiển thị câu trả lời, đồng thời lưu thông tin cần
   thiết để theo dõi chi phí, độ trễ và phân tích câu trả lời sai.

## Lưu ý khi triển khai

- Kích thước top K và ngưỡng đủ bằng chứng cần được hiệu chỉnh bằng bộ đánh giá.
- Trích dẫn hợp lệ không tự chứng minh đáp án đúng; cần kiểm tra độ đúng và mức bám nguồn.
- Web có thể nhận token qua SSE ngay khi model đang sinh. Sơ đồ thể hiện quan hệ
  nghiệp vụ; lưu bản ghi hoàn chỉnh khi kết thúc lượt trả lời.
- Thinking và non-thinking là lựa chọn của bước gọi DeepSeek, không thay thế retrieval.
- Nội dung từ kho tri thức và web là dữ liệu tham khảo, không phải chỉ dẫn hệ thống.

Đọc kèm: [kiến trúc dự án](04_ARCHITECTURE.md) và [techstack](01_TECHSTACK.md).
