# Kiến trúc và quyết định Milestone 1

## Quyết định rút gọn

- **Monolith Python FastAPI + SQLite**: bỏ Redis, Celery, microservices, vector DB, Docker; chưa cần cho một thư viện cá nhân.
- **Parser EPUB dùng standard library + BeautifulSoup**: đọc trực tiếp file OPF và spine để không phụ thuộc EbookLib cho M1; dùng EbookLib sau nếu gặp EPUB thực tế không tương thích.
- **1 file spine XHTML = 1 source unit** trong M1: duy trì tính ổn định ID và lộ trình trích xuất nguồn; chia theo mục từ/tư duy cần dành cho M2 tùy chế độ.
- **Không quyết định tự động hai file có cùng tác phẩm**: SHA-256 phát hiện chính xác duplicate; tác phẩm và ấn bản khác có thể nối bằng thao tác người dùng.
- **Hai FTS index tách biệt**: `source_fts` chạy thực tế; `distilled_fts` reserved, trigger chỉ lập chỉ mục bản `published`. Tránh tìm nhầm lời AI như trích dẫn nguyên văn.
- **Tác phẩm (books) → ấn bản (editions) → source_files → content_units**: định danh UUID và vị trí `href`. Bản ebook không có số trang in ổn định.

## Tính toàn vẹn và data lineage

- `source_files.sha256` UNIQUE; bản EPUB lưu trong `epubs/<sha256>.epub`, không sửa.
- Mọi bảng lõi dùng FOREIGN KEY; `content_units` UNIQUE theo file và spine_index; FTS5 external content triggers trong cùng DB transaction.
- Mỗi lần nhập một EPUB: đọc file, parse EPUB, khóa ghi SQLite `BEGIN IMMEDIATE`, insert toàn bộ unit, COMMIT. Khi parse hỏng hoặc DB lỗi: không ghi dở nửa sách; file mới không được tham chiếu sẽ xóa.
- `source_fts` từ `content_units` có thể rebuild. Index `distilled_fts` sử dụng content-retaining FTS, chỉ công bố `published` và có thể rebuild từ distilled_units.
- `PRAGMA journal_mode=WAL`, `foreign_keys=ON`, `busy_timeout`, `synchronous=FULL`; backup qua SQLite Online Backup API.

## Cần bổ sung ở Milestone 2/3

1. Task durable queue với lease/worker heartbeat, idempotency key cho mỗi `run_id + unit_id`, retry giới hạn, pause/resume và atomic commit.
2. Các chunk có ranh giới ngữ nghĩa; dictionary entry có thể trải qua nhiều nguồn EPUB blocks. Không mặc định part == entry.
3. JSON Schema/Pydantic validation + verify evidence quote và vị trí nguồn, kiểm toán ngữ nghĩa theo chính sách. Chỉ hiện trong distilled search khi được phép publish.
4. Bảo mật khóa API, ngân sách, rate limit, log redaction; model/prompt provenance; revision immutable.
5. Khả năng phục hồi khi kill process và mất điện; test run thực trên Windows, EPUB thật và API model thật.
6. So sánh engine cũ trên source thật trước khi import checkpoint 24/763; không sửa hay chạm dữ liệu cũ.

## Giới hạn bản nghiệm thu này

- Nghiệm thu kỹ thuật local với EPUB thử nghiệm; chưa có EPUB thực tế của người dùng trong môi trường và không thể tuyên bố tương thích với mọi EPUB.
- Chưa hỗ trợ chế độ từ điển đa block, chưa OCR, chưa markdown export hay Google Drive sync.
- UI chưa có xử lý AI, không trình bày trạng thái distillation giả.

---

## Bổ sung v0.2.0 — Milestone 2

- `engine.py` lưu run/job state vào SQLite; chỉ một worker trong mỗi tiến trình, atomic lease đồng thời bảo vệ khi nhiều tiến trình dùng cùng DB. Mỗi run chỉ có tối đa một request `processing` chưa hết lease.
- `providers.py` gọi OpenAI Responses API, đọc API key từ biến môi trường, parse JSON Schema và usage; không log payload hoặc secret.
- `distillation.py` chứa prompt version + Pydantic schema + kiểm tra câu quote chính xác trong nội dung nguồn. Không gọi đây là semantic audit.
- `0003_incremental_engine.sql` thêm thông tin lease, budget telemetry và JSON checkpoint. Chu trình: **claim -> provider call -> checkpoint response -> code audit & publish in transaction**. FTS trigger trong M1 schema phụ trợ chỉ đánh chỉ mục khi `status='published'`.
- `search.py` UNION FTS hai nguồn, giữ provenance và bộ lọc `scope=source|distilled|all`.
- UI xử lý theo `processing_run`, tìm kiếm và `knowledge`. Endpoint form `POST` có Origin check, Host được whitelist để tránh DNS rebinding trên ứng dụng localhost.
- Khôi phục sau crash: với bản `drafted` đã commit, worker re-audit không gọi API; với request bị crash trước ghi checkpoint, có thể phải gọi lại API và phát sinh phí, không có bảo đảm exactly-once network.
- Phạm vi: chỉ XHTML unit từ M1; các unit vượt `max_source_chars` được đánh `needs_review`, không cắt cụt. Dictionary Mode không khẳng định đã tách entry chuẩn.
