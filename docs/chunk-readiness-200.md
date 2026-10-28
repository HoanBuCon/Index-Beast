# Đánh giá cấu trúc 200 trang trước chunking

Ngày: 28/10/2026. Phạm vi: nghiên cứu offline của TV2 Sprint 2, trên artifact processed sau làm sạch, không thực thi embedding/indexing hoặc API AI.

## Kết luận

**Phù hợp để thử nghiệm chunking có cấu trúc; chưa sẵn sàng đưa toàn bộ 200 trang thẳng vào index.** Có heading, block, ID, provenance và metadata đủ để tạo prototype. Phải xử lý riêng đoạn ngắn/hội thoại và bổ sung một số ngữ cảnh trước khi chốt chunker production. Chất lượng retrieval chưa được đo trong nghiên cứu này.

Nguồn: job crawl-adfa0d316047; thư mục backend/data/clean_runs/s2-csv-200-v1. Kiểm tra checksum cả ba CSV theo report; section processed được đối chiếu content_hash với lore_clean.csv. Nghiên cứu đọc đúng 200 ID, giữ nguyên input. Tokenizer intfloat/multilingual-e5-small có sẵn trong cache local; không tải tokenizer/model mới và không chạy encoder. Hash tokenizer: 0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39.

## Phạm vi thực sự có thể chunk thử

- 1.353 section: 783 base theo heuristic, 564 review và 6 excluded.
- 154/200 trang có ít nhất một section base; 46 trang chưa có section đủ căn cứ để giữ.
- Corpus thử nghiệm chunking mặc định chỉ dùng 783 section được giữ. Không tự đưa review/excluded vào cùng index base hoặc gán base hàng loạt.
- Base vẫn là nhãn từ quy tắc có evidence, chưa phải xác minh thủ công mọi phát biểu. Mẫu được chọn theo category và thứ tự discovery, không phải mẫu ngẫu nhiên toàn wiki và chưa chứng minh đủ độ phủ lore cho RAG hoàn chỉnh.

## Phân bố độ dài

Đếm bằng tokenizer thực, tắt truncation/padding. Body là text section; serialized là `passage: title + section + body` có special tokens. Percentile dùng nearest rank.

| Chỉ số | Body | Toàn chuỗi serialized |
|---|---:|---:|
| Nhỏ nhất | 2 | 11 |
| Trung vị | 42 | 53 |
| P90 | 240 | 253 |
| P95 | 420 | 432 |
| P99 | 3,157 | 3,167 |
| Lớn nhất | 7,083 | 7,095 |

| Độ dài body | Số section | Tỷ lệ trong 783 |
|---|---:|---:|
| Dưới 50 token | 439 | 56,1% |
| 50–99 token | 164 | 20,9% |
| 100–299 token | 119 | 15,2% |
| Từ 300 token | 61 | 7,8% |

603 section, khoảng 77%, dưới 100 token. Do đó không đặt tối thiểu cứng 300 token: ghép cho đủ số có thể trộn chủ đề, người nói, điều kiện hoặc scope. Có thể giữ chunk ngắn hoàn chỉnh, hoặc ghép section kề tương thích khi giữ được subheading.

33 section vượt 450 token khi tính toàn chuỗi; 29 vượt 512, 15 vượt 1.000. Dù chỉ một tỷ lệ nhỏ section quá dài, chúng mang lượng nội dung lớn nên truncation sẽ làm mất đáng kể ngữ cảnh.

## Cấu trúc block phù hợp với những cách chia khác nhau

| Loại block trong tập base | Số block | Trung vị token | Max token | Vượt 450 |
|---|---:|---:|---:|---:|
| dialogue | 43 | 1177 | 3792 | 27 |
| infobox | 445 | 10 | 69 | 0 |
| prose | 1734 | 15 | 307 | 0 |
| quote | 29 | 39 | 70 | 0 |
| table | 15 | 71 | 236 | 0 |

Prose có thể đóng gói theo block/đoạn nguyên vẹn trước; max body một block chỉ 307 token trên tập này. Không cần bắt đầu bằng việc chặt giữa câu. Các bảng điều kiện vật phẩm được giữ hiện tối đa 236 token; ưu tiên giữ header và hàng cùng nhau. Infobox có nhiều trường nhỏ, phù hợp giữ dạng thuộc tính/context thay vì mỗi trường là một chunk rời.

### Hội thoại là điểm cần sửa đầu tiên

43 block dialogue, 27 block vượt 450 token. Từ raw DOM tìm lại được 860 ô th trong các bảng này; đây là số ô header, không đồng nghĩa 860 trigger đã xác minh. Processed giữ thứ tự dòng nhưng không có typed turns hay trường trigger/speaker riêng. Nhiều section gộp cả English và Japanese nên lang=unknown.

Chunking trực tiếp theo cửa sổ token có thể giữ câu trả lời nhưng làm rơi điều kiện kích hoạt ở đầu bảng. Nên đọc lại raw bằng location đã lưu để tạo các đơn vị có cấu trúc: language, trigger, speaker khi nguồn nêu rõ, utterances, DOM locator. Không suy người nói từ title nếu bảng có nhiều nhân vật. Khi một lượt thoại vẫn quá dài, chia theo câu/đoạn và lặp lại context trigger/người nói vào mỗi chunk.

| Ví dụ section Dialogue | Body token |
|---|---:|
| Alexander, Warrior Jar | 7,083 |
| Brother Corhyn | 4,995 |
| Blaidd the Half-Wolf | 4,767 |
| Boc the Seamster | 4,537 |
| Bloody Finger Hunter Yura | 3,875 |

### Heading trùng và thiếu anchor

Có 91 nhóm đường dẫn heading trùng trên 56 trang trong toàn bộ tập processed, do nhiều biến thể boss/địa điểm có cùng heading. Ví dụ Ancient Hero of Zamor có ba section `Bosses > Background`. Không dùng title + section text làm khóa duy nhất; giữ record_id, DOM location và ordinal/variant context.

783 section base đều có DOM locator. Tuy nhiên, 508 section base có heading (không tính Introduction/Infobox) đều đang thiếu anchor. MediaWiki thường đặt id trong span.mw-headline bên trong h2/h3, nên cần khôi phục từ raw trước khi tạo URL trỏ thẳng tới section. Hiện URL trang và revision vẫn truy nguồn được; đây là thiếu sót về mức chi tiết trích dẫn, không phải mất toàn bộ provenance.

## Metadata và ảnh

- Có record_id, doc_id ở document, title, section, source, URL, revision, fetched_at, source snapshot, block location, source_type/lang và image_ids.
- 217 section base có source_type unknown; 123 có lang unknown. Không tự coi unknown là tiếng Anh hoặc wiki prose. Tách bảng ngôn ngữ theo nhãn nguồn trước khi gán metadata cụ thể hơn.
- 200 tài liệu thiếu updated_at. Phải thống nhất đó là thời điểm nguồn sửa hay thời điểm pipeline xử lý; không đồng nhất fetched_at với thời điểm sửa nguồn nếu chưa có bằng chứng.
- 83/783 section base có image_ids. Khi một section bị chia, chỉ truyền ảnh có association hợp lệ; không nhân mọi ảnh của trang vào mọi chunk. Không có OCR, image embedding hay retrieval ảnh trong nghiên cứu này.
- Chunker sau này cần bổ sung chunk_id, token_count, section_record_id, ordinal và dấu vết boundary/overlap; không phải các trường đã có sẵn trong CSV hiện tại.

## Thử các ngân sách token

Dưới đây chỉ là **ước lượng số cửa sổ token**, giữ section độc lập và chưa gộp đoạn ngắn. Dùng prefix budget xấp xỉ, không xuất chunk thật hoặc xác nhận ranh giới ngữ nghĩa. Chunker triển khai phải encode lại chuỗi cuối sau khi thêm title, trigger và context.

| Cap tổng token | Overlap | Cửa sổ ước lượng |
|---|---:|---:|
| 350 | 0 | 965 |
| 350 | 50 | 986 |
| 400 | 0 | 931 |
| 400 | 50 | 950 |
| 450 | 0 | 908 |
| 450 | 50 | 918 |
| 500 | 0 | 891 |
| 500 | 50 | 901 |

450/50 cho khoảng 918 cửa sổ trước gộp đoạn ngắn, so với 986 ở 350/50. Số cửa sổ không chứng minh chất lượng retrieval; chưa có benchmark để gọi một lựa chọn là tối ưu.

## Chiến lược đề xuất cho prototype

1. Giữ hard cap 450 token tính cả title/section/context và special tokens, theo hướng ADR-003. Không đặt body 450 rồi cộng prefix sau.
2. Giữ chunk ngắn nếu đủ nghĩa. Chỉ ghép section kề cùng trang, heading cha, scope, source_type và ngôn ngữ khi không làm mất chủ đề; giữ các subheading. Unknown không được tự coi là tương thích.
3. Prose: gom paragraph/block nguyên vẹn đến giới hạn; chỉ chia giữa đoạn khi thật sự cần.
4. Dialogue: tách English/Japanese và trigger/turn từ raw table trước; mang context vào mỗi chunk. Không cắt bảng thoại như văn bản phẳng.
5. Overlap khoảng 30–50 token trong cùng section khi cần chia dài; không áp overlap máy móc cho section ngắn hoặc xuyên scope/nhân vật.
6. Giữ table header với hàng liên quan và giữ variant context cho heading lặp. Dùng section_record_id + ordinal để định danh chunk.
7. Bổ sung anchor và chốt ý nghĩa updated_at trước khi cố định metadata contract. Chỉ dùng image_ids đã liên kết hợp lệ.
8. Kiểm chứng prototype bằng token budget, text coverage, trigger coverage, boundary examples và duplicate IDs. TV3 đánh giá retrieval sau đó; không tự triển khai thay phần TV3.

## Thứ tự ưu tiên

- P1: lấy lại typed dialogue units từ raw; khôi phục anchor và ngữ cảnh biến thể.
- P2: chunk prototype có kiểm ngân sách thực và metadata đầy đủ trên tập base đủ căn cứ; tiếp tục review 564 section.
- P3: review boundary trên ví dụ dài/ngắn, rồi phối hợp TV3 đo retrieval và hiệu chỉnh tham số.

Hiện có thể bắt đầu prototype trên phần prose/description có scope đủ căn cứ và cấu trúc rõ. Toàn bộ 200 trang chưa phải corpus sẵn sàng index production. Nghiên cứu này không sửa CSV, không sửa chunker production và không thay trạng thái ADR-003 đã đề xuất.

## Tái lập nghiên cứu

Từ backend, dùng tokenizer local có sẵn và output mới/rỗng:

```powershell
.venv/Scripts/python.exe -m ingest.debug.chunk_readiness --input data/clean_runs/s2-csv-200-v1 --tokenizer "<duong-dan-tokenizer.json-local>" --output data/studies/another-chunk-study
```

Script không có mã tải tokenizer hoặc model. JSON kết quả lưu thống kê từng section/block và ví dụ raw headers để kiểm tra. Ruff check/format của script đạt; các invariants cohort, checksum CSV, content_hash processed, revision/DOM locator và input không đổi đã được kiểm tra khi chạy. Không chạy lại toàn bộ test backend vì không sửa logic production trong tác vụ nghiên cứu này.


## Cập nhật sau nghiên cứu

Các số liệu trên phản ánh clean v1. Prototype clean v2/chunker đã được triển khai sau nghiên cứu, xem [bàn giao](handover/2026-10-28_s2-tv2_chunking-co-cau-truc.md). Dữ liệu nghiên cứu gốc và CSV v1 được giữ nguyên.
