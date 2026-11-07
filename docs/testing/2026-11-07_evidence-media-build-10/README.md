# Chẩn đoán evidence / ảnh / build — 07/11/2026

TV3 MinhMuc · `feature/s3-tv3-evidence-media-build` · không commit/push/merge.

## Kết quả thật, không thay bằng kết quả offline

Run **complete, 10/10 lượt**: **7 HTTP 200, 3 HTTP 502**. Không replay, không lượt11.
39 logical DeepSeek calls, SDK retry=0; 4 Tavily HTTP requests = 2 Search + 2 Extract.
Known usage: 220.307 prompt tokens, 9.899 completion tokens; một SSE call thiếu usage.
Median latency 10.231 ms, min 1.634 ms, max 21.722 ms (bao gồm các lượt lỗi nhanh).
Qdrant corpus trước/sau **18.368 point**, không index/drop/recreate corpus.
DB và memory collection test riêng được giữ nguyên, tên trong [report.json](report.json).

| ID | Mode | HTTP | Calls | Giây | Ảnh trả về | Kết quả đọc thực tế |
|---|---|---|---|---|---|---|
| EMB01 | off | 200 | 5 | 10,12 | 2 local | Rivers of Blood đúng chủ thể, hai kích thước; text vẫn nói thiếu ảnh |
| EMB02 | off | 200 | 5 | 8,94 | 3 local | Arsenal Charm đúng chủ thể nhưng cùng hash lặp ba lần |
| EMB03 | off/SSE | 200 | 5 | 10,34 | 3 local | Ranni, có cả cutscene; SSE done thành công, text phủ nhận gửi ảnh |
| EMB04 | always | 200 | 4 | 12,30 | 0 | Reduvia Search+Extract, nguồn có 5 STR/13 DEX/13 ARC; không có web-image candidate đủ association |
| EMB05 | always | 200 | 6 | 13,49 | 1 local | Vị trí Dark Moon Greatsword, ảnh đúng kiếm nhưng ảnh local, không phải web |
| EMB06 | auto | 200 | 5 | 15,91 | 0 | Vagabond/Zweihander: calculator lỗi source chưa fetch rồi lỗi schema; không có checked_build |
| EMB07 | auto | 502 | 1 | 1,98 | 0 | Hero/Great Stars: model dịch constraint goal thay vì trích nguyên substring user |
| EMB08 | auto | 200 | 6 | 21,72 | 3 local | Bandit/Reduvia: chỉ có định hướng Dex/Arc, chưa có bảng8 đã kiểm; ảnh Reduvia nhiều kích thước |
| EMB09 | auto | 502 | 1 | 1,63 | 0 | Model hỏi3 field, schema giới hạn2; chưa tạo clarification pending |
| EMB10 | off | 502 | 1 | 1,69 | 0 | Query làm mất Moonveilll-X và phủ định; không kiểm được resume vì lượt9 lỗi |

**Không phải 7 đáp án hoàn toàn đúng.** Các lỗi thiếu dữ liệu, text/ảnh không đồng bộ và build chưa đạt được giữ nguyên.
`review.json` là nhận xét do trợ lý đọc đáp án/quotes và mở ảnh, chưa có review độc lập của thành viên khác.
`report.json` chứa raw model outputs, response, trace, calls, nguồn và lỗi thật; expected không đưa vào model/evidence.
Thời điểm UTC trong report là 06/11 buổi tối, tương ứng sáng07/11 tại Asia/Saigon.

## Ảnh đã kiểm

12 image entries, 10 blob độc nhất: tất cả GET200, MIME raster, decode và SHA-256 đúng.
Đã mở cả10 file trong `images/`: Rivers of Blood, Arsenal Charm, Ranni, Dark Moon Greatsword và Reduvia;
không thấy Uchigatana/Nagakiba/menu icon thay cho chủ thể trong tập này. Có ảnh trùng và cutscene không cần thiết.
Đây là kiểm file ảnh do trợ lý quan sát, không phải browser UI visual QA hay phép đánh giá VLM độc lập.
License/attribution vẫn unknown khi artifact không cung cấp.

**Chưa có ảnh web thành công thật.** Hai lượt always đã gọi Tavily thành công nhưng không có candidate ảnh web
đủ liên kết trang để phát cho client. Ảnh kiếm ở EMB05 là local, không được tính thành công pipeline web.
Downloader public-IP/TLS/hash/cache và association web được kiểm offline bằng fake HTTP/model; điều đó không thay
cho một lần fetch ảnh thật từ provider. Không tự gán ảnh global Tavily vào citation hoặc crawl bù.

## Build đã kiểm

Không có generic checked_build nào trong run thật. Không được ghi ba build ngoài cặp cũ là đã đạt.
Ở EMB06, hai proposal model đều có tổng139; phép cộng Python độc lập khớp công thức level60+79.
Nhưng source class chưa được fetch, rule/cap không đủ, một proposal còn sai schema; tổng đúng **không** chứng minh
class inputs/provenance đúng, không phải calculator pass và không phải build phù hợp/tối ưu.
EMB07 dừng trước tool; EMB08 chỉ trả hướng dẫn định tính. Chưa đo AR/DPS/soft cap/hiệu quả thực chiến.

## Sửa sau run, chỉ xác minh offline

- Agent decision được repair tối đa1 lần với validation feedback, vẫn nằm trong deadline và 6 calls chung,
  giữ1 call cho generation. Chỉ repair object đầy đủ nhận diện được, không nới provenance/schema.
- Regressions từ ba decision thật được lưu thành fixture; scripted model trả bản sửa hợp lệ để kiểm đường recovery.
  Test vẫn kiểm lỗi không sửa được và hết budget; không đổi HTTP502 thật thành kết quả đạt.
- Prompt yêu cầu constraint giữ nguyên ngôn ngữ user, query giữ mọi tên/phủ định, tối đa2 field clarification.
- Calculator observation bổ sung lỗi validation cụ thể để planner tìm dữ liệu thay vì đoán lại quote/schema.
- Text generator được thông báo ảnh do backend xử lý sau; không phủ nhận khả năng gửi ảnh.
- Dedup ảnh cùng hash, yêu cầu ưu tiên một ảnh chính/chủ thể; chưa test hiệu quả chọn ít ảnh bằng API thật lần nữa.
- Giữ ID web gốc khi chọn evidence, tránh dedup trước selection làm mất ID đã được model chọn.
- Kiểm không nhét bảng/chỉ số khác vào prose khi đã có checked artifact.

Baseline **817 passed / 2 warnings**; trước run **889 passed / 2 warnings**;
sau sửa **915 passed / 2 warnings**. Hai warning cũ: Qdrant memory payload index và Alembic path_separator.
41 web tests pass, TypeScript và Vite build pass. Ruff lint/format, pip check, OpenAPI check pass.
Không có browser/Discord gateway test, không thay UI TV4, `.env`, model weights hoặc dữ liệu gốc.

Lệnh plan/execute/resume và contract: [evidence-media-build.md](../../api/evidence-media-build.md).
Chạy mới phải dùng output mới; không resume run complete để cố retest những lượt cũ.
Ngân sách 10 lượt đã dùng hết; các sửa sau run chưa có bằng chứng thành công API thật.


Log kiểm tra cuối: [backend offline](offline-final.txt), [web tests](web-tests.txt), [plan](plan.json).
Execution log đầy đủ giữ local trong `execution.log` (file log có thể bị gitignore); raw report vẫn được giữ riêng.


## ?nh ki?m th? v? Git ? 08/11/2026

Th? m?c `images/` l? b?n raster sinh ra khi benchmark ?? m? ki?m tra t?i m?y ch?y.
C?c ?nh gi? nguy?n byte/hash v? c?n tr?n m?y; th? m?c n?y ???c gitignore, kh?ng ??ng g?i trong commit.
Hook gi?i h?n file m?i1MiB ?? ch?n hai PNG1.452KB v?1.350KB; kh?ng n?ng ng??ng ho?c b? hook.
M?y clone m?i v?n ??c ???c report/hash/nh?n x?t nh?ng kh?ng c? c?c file `inspection_file` tr?n m?y ng??i ch?y.
N?u c?n review pixel, chia s? nguy?n blob qua kho artifact ri?ng; kh?ng resize/n?n r?i d?ng l?i hash c?.
