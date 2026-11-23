# Javis Book Intelligence — v0.2.0 (Milestone 2)

**Dữ liệu gốc:** [ĐẶC TẢ DỰ ÁN V2.0.md](ĐẶC%20TẢ%20DỰ%20ÁN%20V2.0.md) (giữ nguyên văn).

**Đã triển khai:** EPUB Library + metadata/edition + SHA-256 (M1), SQLite FTS5 nguồn EPUB (M1), **OpenAI Responses API JSON Structured Outputs**, General/Dictionary prompts, queue SQLite với lease/checkpoint, chưng cất từng đơn vị XHTML, `code audit` (schema + nguyên văn dẫn chứng), `drafted` checkpoint bền vững, transaction publish bản đạt audit + claims/evidence + FTS ngay, bản lỗi `needs_review` không xuất hiện trong chỉ mục chưng cất, Pause/Resume/Stop, bounded retry, ngân sách với dự toán trước từng API call, theo dõi token/chi phí, giao diện Processing Dashboard, tìm kiếm nguồn/bản chưng cất/xuyên sách.

**Chưa triển khai/chưa nghiệm thu:** semantic audit độc lập, kiểm tra đủ ý toàn chương, xử lý trọn mục từ qua nhiều XHTML, tự phân đoạn chương lớn, PDF/OCR, Claude/Ollama, vector search, đồng bộ Google Drive, import checkpoint legacy, ingest Javis runtime thật. **Không có kiểm thử API thực trong môi trường phát triển vì không có API key và nguồn EPUB đã được cấp phép cho bài test.** Các unit test sử dụng *scripted fake provider* và HTTP `MockTransport` để kiểm tra kỹ thuật, **không chứng nhận chất lượng ngữ nghĩa của AI**.

## 1. Cài đặt

Yêu cầu: Python 3.11 trở lên, SQLite có FTS5, Windows 10/11 hoặc Linux/macOS. Không cần Docker, Redis hay server public.

- Windows: chạy `run_windows.bat`.
- Linux/macOS: chạy `./run_linux.sh`.
- Cài bằng tay:

```bash
python -m venv .venv
# Linux/macOS: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install -e ".[test]"
python -m javis_book_intelligence
```

Mở `http://127.0.0.1:8765`. Ứng dụng chỉ bind trên loopback, giới hạn Host và kiểm tra Origin khi có request ghi. Database nằm ở `JAVIS_DATA_DIR/library.db` (mặc định `~/.javis_book_intelligence/library.db`), EPUB trong `epubs/` dưới cùng thư mục.

### Thiết lập API key tại máy của bạn

Tạo một **OpenAI API key cho API có thanh toán riêng**. Subscription ChatGPT không thay thế API key. **Không gửi key qua chat và không commit lên GitHub.**

Trong PowerShell (chỉ phiên terminal hiện tại):

```powershell
$env:OPENAI_API_KEY = "<nhập-key-của-bạn-tại-máy>"
python -m javis_book_intelligence
```

Trong Windows CMD: `set OPENAI_API_KEY=<nhập-key-của-bạn-tại-máy>`; trong Linux/macOS: `export OPENAI_API_KEY='<nhập-key-của-bạn-tại-máy>'`. Những dòng trên chỉ là cú pháp mẫu, không có key thật. API key chỉ được đọc từ biến môi trường khi gửi HTTPS tới `https://api.openai.com/v1/responses`; chương trình không lưu key vào SQLite, JSON, log hay backup.

## 2. Dùng Milestone 2

1. Nhập EPUB không DRM tại **Thư viện**. Mở trang chi tiết cuốn sách.
2. Chọn **General** (sách thường) hoặc **Dictionary** (xử lý theo XHTML, **không đảm bảo ranh giới một mục từ**), nhập **mã model API có hỗ trợ Structured Outputs**, chọn số đơn vị tối đa cho lượt chạy (mặc định 20), giới hạn source chars/output tokens.
3. **Kiểm tra đơn giá API thực tế tại thời điểm dùng và tự nhập USD/1 triệu input và output tokens.** Giá trong biểu mẫu không được suy diễn tự động; chi phí là ước tính theo đơn giá bạn cung cấp, token usage là số mà API trả về.
4. Xác nhận ngân sách USD và nhấn **Start** đúng một lần. Hệ thống tạo `processing_runs` và `jobs` trong cùng transaction. Worker tự làm các đơn vị đã cấp phép, không cần bấm OK cho mỗi chương.
5. Theo dõi **Chưng cất AI**: `pending`, `processing`, `drafted`, `retry_waiting`, `completed`, `needs_review`, `failed`; bấm Pause/Resume/Stop. Stop không xóa dữ liệu; request đang bay có thể hoàn tất và được commit trước khi dừng.
6. Qua **Tìm kiếm**, chọn phạm vi **Cả nguồn và chưng cất / Chỉ nguồn / Chỉ chưng cất**. Bản chưng cất được tìm ngay sau khi một đơn vị đạt code audit, dù toàn sách vẫn xử lý.
7. Mở tri thức để đọc nội dung, model/prompt version, nhận định, dẫn chứng nguyên văn, vị trí EPUB, audit và revision history. `needs_review` không được index.

**Lưu ý về dữ liệu gửi ra ngoài:** khi khởi chạy với OpenAI, văn bản của đơn vị EPUB được gửi tới nhà cung cấp API. Chỉ xử lý sách/tư liệu bạn có quyền cho phép chuyển cho bên thứ ba.

## 3. Cơ chế lưu liên tục, phục hồi và giới hạn

- Mỗi job bám vào `content_units.id` và `source_files.id`; `sha256` của source text được ghi lúc claim. Không tự cắt đầu/đuôi của XHTML quá dài: đơn vị lớn hơn `max_source_chars` được đưa vào `needs_review` để chia nhỏ theo cấu trúc ở milestone sau.
- Transaction 1: **claim lease** + source hash + attempts. Gọi API ở ngoài transaction để tra cứu không bị chặn. `response.status` phải completed, JSON đúng schema, `usage` hợp lệ.
- Transaction 2: **lưu JSON gốc + token usage + giá trị chi phí** và đặt trạng thái `drafted`. Nếu ứng dụng chết sau bước này, job có thể khôi phục từ JSON đã lưu sau lease, **không phải gọi lại API**.
- Transaction 3: code audit dẫn chứng nguyên văn (`quote in source_body`) + upsert distilled draft/revision + claims/evidence + audit report + chuyển `published` + cập nhật FTS (trigger), **cùng một transaction**. Khi transaction lỗi, toàn bộ bước công bố rollback; bản nháp đã checkpoint ở transaction 2 vẫn còn.
- Lần gọi API đang bay lúc app bị tắt: nếu provider đã nhận request nhưng chưa ghi response về SQLite, có thể xảy ra **gọi lại và tốn phí hai lần**. Không thể cam kết exactly-once qua mạng chỉ bằng SQLite. Lease token ngăn worker cũ công bố/trừ tiền lần nữa sau khi mất quyền.
- Thử lại có giới hạn với HTTP 408/409/429, 5xx hoặc lỗi mạng; phản hồi lỗi key/model không được retry tự động, run có thể pause. Khi cần sửa, làm lại job thủ công (không tự ghi đè bản đã duyệt).
- Budget là **cổng dự toán trước lời gọi**, không phải hard spending cap do nhà cung cấp cấp phép. Dự toán input dùng UTF-8 bytes như một heuristic bảo thủ, output dùng `max_output_tokens`, chỉ có một request đang chạy cho mỗi run. **Chi phí thực tế có thể vượt budget** nếu usage khác dự toán, giá nhập sai, API có phụ phí hoặc request mất kết nối sau khi đã bị tính tiền. Nên đặt hard limit độc lập trên dashboard nhà cung cấp, thử 1–2 đơn vị trước.
- `code audit` chỉ chứng nhận **đúng cấu trúc và quote xuất hiện nguyên văn**, **không chứng minh quote hỗ trợ lập luận, diễn giải đúng, hay không bỏ sót nội dung**. `semantic audit` độc lập là Milestone 3.
- SQLite là nguồn dữ liệu chính, EPUB gốc được giữ. Không đồng bộ trực tiếp SQLite đang ghi. Dùng SQLite Backup API, xuất/copy backup nhất quán và giữ EPUB nguồn khi khôi phục.

## 4. Kiểm thử

```bash
python -m pip install -e ".[test]"
python -m pytest -q
python scripts/benchmark_search.py --units 10000 --queries 100
```

Bộ test phát sinh EPUB hợp lệ thực và kiểm tra source parser, metadata, FTS5, rollback, durability, lỗi quote/schema, retry, pause/stop, ngân sách, lease stale, checkpoint `drafted`, source drift, phân quyền cùng-origin, giao diện/API. **Không sử dụng fake để tuyên bố chất lượng AI đã đạt**.

### Smoke test bằng API thực (tùy chọn, có phí)

Chỉ chạy sau khi bạn có EPUB có quyền xử lý, API key, mã model và đơn giá được kiểm tra; **chỉ gửi tối đa một đơn vị XHTML**. Đọc output/claims và kiểm toán thủ công ngay sau đó.

```bash
python scripts/smoke_openai.py --epub "duong-dan/sach.epub" --model "ID_MODEL_CUA_BAN" \
  --input-price 1 --output-price 4 --budget 0.5 --confirm-send-to-openai
```

Các mức giá `1` và `4` trong ví dụ là **giá giả định**, thay bằng đơn giá thực tế trước khi chạy. Nếu không thêm `--data-dir`, script dùng thư mục tạm và xóa sau khi kết thúc. Nếu bạn muốn giữ data để kiểm tra: `--data-dir ./my-local-smoke-test` (**không commit** thư mục này).

## 5. Kiến trúc

```text
javis_book_intelligence/
  db.py             SQLite connect, transaction, migrations, backup, rebuild FTS
  epub.py           EPUB parsing (M1)
  service.py        EPUB/metadata management (M1)
  search.py         FTS5 source + distilled + combined, filter and pagination
  distillation.py   Versioned prompt + strict Pydantic schema + source quote audit
  providers.py      OpenAI Responses adapter; key only from environment
  engine.py         Durable queue, leases, cost, retry, checkpoints, evidence, publish
  web.py            FastAPI + import/search/processing/knowledge UI/API
  migrations/       0001 M1, 0002 reserved schema, 0003 M2 additive
  templates/static/ Jinja UI and safe text rendering / polling
scripts/smoke_openai.py
scripts/benchmark_search.py
tests/test_library.py, test_web.py, test_m2_engine.py
```

**Không** tự động mở Batch 13, không sửa plugin/checkpoint Javis v0.1.2 và không ghi vào folder Google Drive cũ. Thông tin legacy cần migration và đối soát riêng ở Milestone 4.
