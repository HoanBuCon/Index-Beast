# Pipeline hệ thống IndexBeast


## A. Monkey

IndexBeast là trợ lý hỏi đáp về Elden Ring trên web hoặc Discord. Nhóm chuẩn bị kho tài liệu trước; khi bạn hỏi, hệ thống tìm những đoạn liên quan và dùng chúng để viết câu trả lời kèm nguồn.

```mermaid
graph TD
    subgraph KNOWLEDGE["Nhóm chuẩn bị kho kiến thức trước"]
        K1["Thu thập tài liệu và ảnh về Elden Ring"]
        K2["Làm sạch, phân loại và kiểm tra dữ liệu"]
        K3["Chia tài liệu thành các đoạn có ghi nguồn"]
        K4[("Kho kiến thức có thể tìm kiếm")]
        K1 --> K2 --> K3 --> K4
    end

    subgraph ASK["IndexBeast"]
        U1["Mở web hoặc dùng lệnh /ask trên Discord"]
        U2["Đặt câu hỏi bằng tiếng Việt hoặc tiếng Anh"]
        U3["IndexBeast xét câu hỏi và ngữ cảnh hội thoại"]
        U4{"Câu hỏi có phù hợp và đủ rõ?"}
        U5["Giải thích giới hạn hoặc hỏi lại để làm rõ"]
        U6["Tìm các đoạn tài liệu liên quan"]
        U7{"Nguồn có đủ để trả lời?"}
        U8["Trả lời phần có căn cứ; nói rõ điều còn thiếu"]
        U9["AI soạn câu trả lời dựa trên tài liệu tìm được"]
        U10["Hệ thống kiểm tra định dạng và liên kết trích dẫn"]
        U11["Nhận câu trả lời, nguồn và ảnh nếu có trên giao diện hỗ trợ"]
        U12["Đọc nguồn, hỏi tiếp hoặc gửi phản hồi"]
        U1 --> U2 --> U3 --> U4
        U4 -->|"Cần làm rõ / ngoài phạm vi"| U5
        U4 -->|"Phù hợp"| U6
        U6 --> U7
        U7 -->|"Thiếu một phần hoặc toàn bộ"| U8
        U7 -->|"Có căn cứ"| U9
        U9 --> U10 --> U11 --> U12
        U8 --> U11
        U5 --> U12
    end
    K4 --> U6
```

Ví dụ: bạn hỏi “Cha mẹ Ranni là ai?”, hệ thống tìm đoạn nói về Ranni rồi soạn đáp án tiếng Việt kèm nguồn. Với câu hỏi về chỉ số chưa có trong kho, hệ thống cần nói rõ phần chưa tìm được; không bảo đảm mọi câu hỏi gameplay đều có đáp án.


### A1. Luồng khi người dùng gửi một câu hỏi

Sơ đồ dưới đây đi theo một lượt hỏi đáp, sử dụng kho kiến thức đã được nhóm chuẩn bị trước.

```mermaid
graph TD
    Q1["Bạn gửi câu hỏi trên web hoặc Discord"]
    Q2["Hệ thống tiếp nhận và đọc ngữ cảnh cuộc trò chuyện"]
    Q3{"Câu hỏi thuộc phạm vi và đủ rõ?"}
    Q4["Giải thích phạm vi hoặc đề nghị bạn nói rõ hơn"]
    Q5["Chuẩn bị từ khóa tìm kiếm; có thể chuyển ý hỏi sang tiếng Anh"]
    Q6["Tìm trong kho kiến thức đã có"]
    Q7["Chọn tối đa 5 đoạn liên quan, kèm thông tin nguồn"]
    Q8{"Có đoạn nguồn dùng được?"}
    Q9["Thông báo chưa tìm được bằng chứng phù hợp"]
    Q10["AI đọc câu hỏi, lịch sử và các đoạn nguồn"]
    Q11["Soạn đáp án đúng trọng tâm; hỏi tiếng Việt thì trả lời tiếng Việt"]
    Q12["Nêu phần có căn cứ và phần còn thiếu; gắn trích dẫn"]
    Q13{"Kết quả qua kiểm tra định dạng và trích dẫn?"}
    Q14["Gắn ảnh nếu ảnh liên kết hợp lệ với nguồn được trích"]
    Q15["Hiển thị đáp án và nguồn; ảnh tùy khả năng giao diện"]
    Q16["Bạn mở nguồn hoặc hỏi tiếp trong cuộc trò chuyện"]
    Q17["Thử phục hồi trong giới hạn; nếu vẫn lỗi thì báo để thử lại"]

    Q1 --> Q2 --> Q3
    Q3 -->|"Không"| Q4
    Q3 -->|"Có"| Q5
    Q5 --> Q6 --> Q7 --> Q8
    Q8 -->|"Không"| Q9
    Q8 -->|"Có"| Q10
    Q10 --> Q11 --> Q12 --> Q13
    Q13 -->|"Đạt"| Q14
    Q13 -->|"Không đạt"| Q17
    Q14 --> Q15 --> Q16
    Q4 --> Q16
    Q9 --> Q16
```

Ví dụ với “Cha mẹ Ranni là ai?”: **nhận câu hỏi → tìm nguồn về gia đình Ranni → chọn đoạn liên quan → AI viết đáp án tiếng Việt → kiểm tra trích dẫn → trả đáp án kèm nguồn và ảnh nếu đủ điều kiện**. Nếu nguồn chỉ trả lời được một phần, IndexBeast cần nói rõ phần còn thiếu. Hệ thống không thu thập lại toàn bộ dữ liệu mỗi khi bạn hỏi.

## B. Ape

### B1. Kiến trúc toàn hệ thống: dữ liệu, ứng dụng và hạ tầng

```mermaid
graph TD
    subgraph DATA["Chuẩn bị dữ liệu · chạy riêng trước khi phục vụ chat"]
        WIKI["Nguồn wiki · TV2"]
        RAW["Raw snapshots + provenance"]
        CLEAN["Clean + content policy + ledger review / excluded"]
        CHUNK["Chunking · text / passage: / metadata / ID"]
        ART[("Artifact JSONL + reports")]
        LOADPG["load_full · validate hash / provenance"]
        PG[("PostgreSQL · documents / chunks / ingestion jobs")]
        ADMIT["CLI index · validation và corpus admission"]
        EMBED["Batch FastEmbed ONNX · E5-small + BM25"]
        UPSERT["Collection schema + upsert idempotent"]
        WIKI --> RAW --> CLEAN --> CHUNK --> ART
        ART --> LOADPG --> PG
        ART --> ADMIT --> EMBED --> UPSERT
    end
    subgraph APP["Ứng dụng phục vụ người dùng"]
    USER["Người dùng / giảng viên"]
    WEB["Web React / Vite · TV4"]
    DISCORD["Discord · lệnh /ask"]
    BOT["Discord bot · TV4"]
    PROXY["Web dev proxy /api"]
    API["FastAPI · /api/v1 · TV1"]
    GUARD["Kiểm tra request, service token và rate limit"]
    REDIS[("Redis · rate limit")]
    SERVICE["Chat service · hội thoại / history / timeout"]
    RAM[("RAM · hội thoại và trace hiện tại")]
    MODE{"CHAT_MODE phía server"}
    MOCK["Mock · dữ liệu giả lập"]
    DIRECT["llm_only · prompt và history có budget"]
    RAG["RAG LangChain · TV3"]
    QDRANT[("Qdrant · dense + sparse BM25")]
    LLM["DeepSeek API · ChatDeepSeek"]
    VALIDATE["Kiểm tra output, citation và quote theo mode"]
    MEDIA["ImageCatalog · ảnh gắn với nguồn được trích"]
    BLOBS[("Media blobs và manifest local")]
    RESPONSE["API response · JSON hoặc SSE trên web"]
    RENDER["Web hiển thị text / nguồn / ảnh; bot hiển thị theo client"]
    HISTORY["GET conversations · lịch sử trong RAM"]
    FEEDBACK["POST feedback · kiểm message_id và xác nhận nhận request"]
    HEALTH["GET health · kiểm tra hạ tầng"]

    USER --> WEB
    USER --> DISCORD
    DISCORD --> BOT
    WEB --> PROXY
    BOT -->|"BOT_API_URL · X-Service-Token"| PROXY
    PROXY --> API
    API --> GUARD
    GUARD <--> REDIS
    GUARD --> SERVICE
    SERVICE <--> RAM
    SERVICE --> MODE
    MODE -->|"mock"| MOCK
    MODE -->|"llm_only"| DIRECT
    MODE -->|"rag"| RAG
    DIRECT --> LLM
    RAG <--> QDRANT
    RAG -->|"Prompt và evidence"| LLM
    LLM --> VALIDATE
    VALIDATE --> MEDIA
    BLOBS --> MEDIA
    MEDIA --> RESPONSE
    MOCK --> RESPONSE
    RESPONSE --> RENDER
    RENDER --> USER
    API --> HISTORY
    HISTORY --> RAM
    API --> FEEDBACK
    FEEDBACK --> SERVICE
    API --> HEALTH
    end
    UPSERT --> QDRANT
    RAW -.->|"Ảnh và manifest thu thập cùng dữ liệu"| BLOBS
    HEALTH -.-> PG
    HEALTH -.-> QDRANT
    HEALTH -.-> REDIS

    subgraph QA["Đánh giá và kiểm thử · chạy riêng"]
        GOLD["Golden set · câu hỏi / đáp án / nguồn kỳ vọng"]
        BENCH["Benchmark retrieval, VI–EN, độ trễ; đánh giá generation khi được phép"]
        REVIEW["Báo cáo + review thủ công / review chéo"]
        GOLD --> BENCH --> REVIEW
    end
    QDRANT -.->|"Đọc khi benchmark thực được chạy"| BENCH
```

- Sơ đồ kết nối trên dùng cách chạy dev chia sẻ qua LAN/Radmin: web bind `0.0.0.0:15173`, proxy tới API `127.0.0.1:18000`. Máy khác dùng IP thật của máy host. Bot cũng có thể gọi thẳng API nếu API được mở mạng riêng phù hợp.
- `CHAT_MODE` do server cấu hình. `llm_only` có thông báo chưa đối chiếu kho tri thức; RAG không tự chuyển sang mode này khi thiếu nguồn.
- Hội thoại live và trace hiện còn trong RAM, không phải lưu bền PostgreSQL. Redis phục vụ rate limit trong luồng này.
- Ảnh chỉ được gắn khi có association hợp lệ với nguồn đã trích. Backend cung cấp ảnh qua `/api/v1/images/{sha256}`; khả năng hiển thị phụ thuộc client. Không mặc định bot Discord đã gửi ảnh.
- PostgreSQL, Qdrant và Redis chạy qua Docker Compose; web, API và bot chạy bằng các target Makefile trong cấu hình dev hiện tại. DeepSeek là dịch vụ API bên ngoài, model embedding chạy local qua FastEmbed ONNX.
- Các mũi tên liền mô tả luồng xử lý/dữ liệu; mũi tên nét đứt mô tả quan hệ hỗ trợ hoặc kiểm tra. Pipeline dữ liệu và benchmark không tự chạy mỗi lần người dùng hỏi.
- `GET conversations` đọc history live từ RAM. Route feedback hiện kiểm message tồn tại và trả `204`, **chưa lưu đánh giá bền**. Không vẽ PostgreSQL như nơi đã lưu toàn bộ hội thoại/feedback.
- Khối đánh giá biểu diễn công cụ và quy trình riêng, không có nghĩa đã đo đủ recall hay hoàn thành review chéo. Admin API hiện còn là khung; crawler Fanapis/entities cũng chưa phải luồng dữ liệu hoàn chỉnh, nên không vẽ như thành phần đã vận hành.

### B2. Chi tiết pipeline RAG khi nhận câu hỏi

```mermaid
graph TD
    INPUT["Câu hỏi + history + ngôn ngữ trả lời"]
    SCOPE{"Scope / injection / tham chiếu mơ hồ"}
    STATIC["Từ chối hoặc yêu cầu làm rõ theo điều kiện"]
    OVERVIEW{"Nhận diện câu hỏi tổng quan?"}
    PLAN["Overview plan · câu gốc + English search focus"]
    REWRITE["Rewrite VI → EN nếu bật · standalone query giữ tên riêng"]
    FALLBACK["Rewrite lỗi: fallback câu gốc hoặc làm rõ tham chiếu"]
    QUERIES["Query plan · original / rewrite / dual · tối đa 2 query"]
    ENCODE["FastEmbed ONNX · E5-small 384 chiều + BM25 sparse · query:"]
    QUERYAPI["Qdrant Query API · dense + sparse prefetch"]
    FILTER["CorpusPolicy · metadata / ngôn ngữ / spoiler"]
    FUSION["RRF trong Qdrant; RRF theo rank nếu nhiều query"]
    RANK["Dedup · reranker tùy chọn; mặc định NoReranker"]
    ORDER["Nếu overview: ưu tiên tiêu đề / section và đa dạng nguồn"]
    CONTEXT["Chọn context tối đa top-5 · budget · policy nhất quán"]
    ENOUGH{"Có context hợp lệ?"}
    NOEVIDENCE["Thông báo thiếu bằng chứng · không tự gọi llm_only"]
    PROMPT["Persona IndexBeast + history + evidence có số thứ tự và metadata"]
    GENERATE["ChatDeepSeek · trả lời đúng ngôn ngữ người dùng"]
    CHECK{"JSON / schema / citation / quote hợp lệ?"}
    RECOVER["Recovery có giới hạn cho lỗi được hỗ trợ"]
    ERROR["Lỗi rõ ràng · SSE không gửi done thành công khi thất bại"]
    OUTPUT["Text + chỉ nguồn thực sự được trích + ảnh hợp lệ nếu có"]

    INPUT --> SCOPE
    SCOPE -->|"Bị chặn hoặc cần làm rõ"| STATIC
    SCOPE -->|"Tiếp tục"| OVERVIEW
    OVERVIEW -->|"Có"| PLAN
    OVERVIEW -->|"Không"| REWRITE
    PLAN --> QUERIES
    REWRITE -->|"Hợp lệ hoặc tắt rewrite"| QUERIES
    REWRITE -->|"Lỗi / timeout"| FALLBACK
    FALLBACK --> QUERIES
    QUERIES --> ENCODE
    ENCODE --> QUERYAPI
    FILTER --> QUERYAPI
    QUERYAPI --> FUSION
    FUSION --> RANK
    RANK --> ORDER
    ORDER --> CONTEXT
    FILTER --> CONTEXT
    CONTEXT --> ENOUGH
    ENOUGH -->|"Không"| NOEVIDENCE
    ENOUGH -->|"Có"| PROMPT
    PROMPT --> GENERATE
    GENERATE --> CHECK
    CHECK -->|"Đạt"| OUTPUT
    CHECK -->|"Lỗi có thể recovery và còn budget"| RECOVER
    RECOVER --> GENERATE
    CHECK -->|"Không thể recovery / hết budget"| ERROR
```

Ngôn ngữ truy xuất tách khỏi ngôn ngữ trả lời: hỏi tiếng Việt có thể tìm bằng tiếng Anh nhưng vẫn trả lời tiếng Việt. Rewrite phụ thuộc cấu hình, không mặc định mọi request đều gọi rewrite. Overview bỏ qua rewrite LLM và dùng query plan xác định bằng code.

Context giữ metadata nguồn, release và giá trị `unknown`; không suy hai nguồn thành cùng canon. Kiểm tra citation/quote là kiểm tra cấu trúc và liên kết evidence, **không phải chứng minh entailment**. Có context chưa đồng nghĩa có đủ đáp án: generator vẫn có thể báo thiếu bằng chứng. Lỗi retrieval/provider được báo riêng, không coi như không có dữ liệu.

### B3. Chi tiết chuẩn bị dữ liệu và indexing

```mermaid
graph TD
    SOURCE["Nguồn wiki / artifact raw đã thu thập · TV2"]
    RAW[("Raw snapshots + provenance; media blobs / manifest")]
    CLEAN["Cleaner · cấu trúc HTML, infobox và ledger loại / review"]
    POLICY["Content policy · keep / review / excluded"]
    CHUNK["Chunker · text + embedding_text passage: + metadata + ID"]
    ARTIFACT[("documents.jsonl / chunks.jsonl / review / reports")]
    PGLOAD["load_full · kiểm provenance / hash và nạp PostgreSQL"]
    PG[("PostgreSQL · documents / chunks / ingestion jobs")]
    DRY["ingest index --dry-run · schema / ID / prefix / policy / thống kê"]
    ADMIT["Index admission · policy pilot và ngôn ngữ được chọn"]
    EMBED["Batch FastEmbed ONNX · multilingual-e5-small + Qdrant/bm25"]
    UPSERT["Kiểm schema collection · upsert idempotent theo point ID ổn định"]
    VECTOR[("Qdrant · dense 384 cosine + sparse BM25 IDF · payload")]
    ONLINE["RAG online truy xuất collection đã cấu hình"]

    SOURCE --> RAW
    RAW --> CLEAN
    CLEAN --> POLICY
    POLICY -->|"Nội dung được chunk theo policy"| CHUNK
    CHUNK --> ARTIFACT
    ARTIFACT --> PGLOAD
    RAW -->|"Đối chiếu raw"| PGLOAD
    PGLOAD --> PG
    ARTIFACT --> DRY
    ARTIFACT --> ADMIT
    ADMIT --> EMBED
    EMBED --> UPSERT
    UPSERT --> VECTOR
    VECTOR --> ONLINE
```

`--dry-run` chỉ validation, không tạo model/client hoặc ghi vector. Nạp PostgreSQL và index Qdrant là hai đường riêng từ artifact; không vẽ PostgreSQL thành bước bắt buộc của mỗi truy vấn chat.


## Mã nguồn và tài liệu đối chiếu

- [RAG pipeline](../backend/app/rag/pipeline.py), [generator](../backend/app/rag/generator.py), [Qdrant store](../backend/core/vector/store.py).
- [Chat service](../backend/app/services/chat.py), [Makefile](../Makefile), [hướng dẫn RAG](../backend/app/rag/README.md).
- [History API](../backend/app/api/routes/conversations.py), [feedback API](../backend/app/api/routes/feedback.py).
- [TV1 sửa cleaner](handover/2026-10-31_s2-tv1_sua-cleaner-bang-chi-so-infobox.md), [TV1 setup và hiện trạng corpus](handover/2026-11-01_s3-tv1_techstack-rag-va-setup-may-tv1.md).
