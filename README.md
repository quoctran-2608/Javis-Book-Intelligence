# Javis Book Intelligence — MVP v0.1.0 (Milestone 1)

**Tài liệu yêu cầu gốc:** [ĐẶC TẢ DỰ ÁN V2.0.md](ĐẶC%20TẢ%20DỰ%20ÁN%20V2.0.md) (nguyên văn bản đặc tả do người dùng cung cấp).

**Thực thi**: Thư viện EPUB không DRM, metadata tác phẩm/ấn bản, SHA-256 chống trùng file, SQLite transaction + versioned migration, nguồn XHTML theo spine EPUB, tìm kiếm keyword/phrase/prefix bằng FTS5, giao diện web trên localhost, sao lưu SQLite an toàn, bộ kiểm thử `pytest`.

**Chưa thực thi**: Gọi AI để chưng cất, kiểm toán ngữ nghĩa, checkpoint/retry AI, quản trị ngân sách API, Google Drive sync, PDF/OCR, semantic search, import Javis legacy. Các bảng `processing_runs`, `jobs`, `distilled_units`, `audit_results`... chỉ là **schema dự phòng**, không phải engine đã vận hành. Không can thiệp checkpoint 24/763, không mở Batch 13.

## 1. Cài đặt và chạy

Yêu cầu Python 3.11+ với SQLite có FTS5, trình duyệt web, Windows 10/11 hoặc Linux. Không cần Docker hay AI key.

**Windows:** giải nén, chạy `run_windows.bat`, chờ cửa sổ ghi địa chỉ `http://127.0.0.1:8765`. Script tạo `.venv` và cài dependencies từ PyPI nên cần Internet lúc cài lần đầu.

**Linux/macOS:** chạy `./run_linux.sh` (nếu máy có `python3` + `venv`).

**Cài thủ công:**

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m javis_book_intelligence
```

Truy cập **http://127.0.0.1:8765**. Ứng dụng chỉ lắng nghe `127.0.0.1` (không công khai ra mạng LAN).

Vị trí mặc định: `~/.javis_book_intelligence/library.db` và `~/.javis_book_intelligence/epubs/<sha256>.epub`. Có thể đổi vị trí qua biến môi trường `JAVIS_DATA_DIR` **trước khi chạy**; xem `config.example.bat` hoặc `config.example.sh`. Không chép trực tiếp database đang mở lên thư mục Drive.

## 2. Sử dụng

1. Chọn/kéo file EPUB (cho phép chọn nhiều file), bấm **Nhập vào thư viện**.
2. Xem sách, sửa metadata và tag; thêm file EPUB khác vào tác phẩm cũ bằng menu **Liên kết với tác phẩm có sẵn**; nếu không chọn, file không trùng tạo tác phẩm mới (hệ thống không đoán cùng tác phẩm từ tiêu đề).
3. Mở **Tìm kiếm**: `Từ khóa` (OR token), `Đúng cụm từ` (FTS phrase) hoặc `Tiền tố` (từ cuối có dấu `*`); kết quả từ nội dung EPUB *gốc được trích xuất*, không phải bản tóm tắt AI.
4. Nhấn kết quả để xem văn bản và đường dẫn tương đối EPUB (`href`), tải EPUB gốc trong hồ sơ sách. Chưa có EPUB reader nhảy trực tiếp đến vị trí đó.

Hỗ trợ tiếng Việt có dấu và phần lớn truy vấn không dấu qua tokenizer `unicode61 remove_diacritics 2`; tiếng Việt/thuật ngữ phiên âm và phân từ phức tạp cần benchmark riêng. Mục lớn một file XHTML = một đơn vị nguồn, chưa phân đoạn theo mục từ từ điển chạy qua nhiều XHTML.

## 3. Kiểm thử

```bash
pip install -e ".[test]"
python -m pytest -q
python scripts/benchmark_search.py --units 10000 --queries 100
# Thử 100K đơn vị khi sẵn sàng:
python scripts/benchmark_search.py --units 100000 --queries 100
```

Bộ test tự sinh EPUB thật theo OPF, container và spine để kiểm tra parser thực; **không dùng đó làm căn cứ nghiệm thu chất lượng AI** (chưa có AI).

## 4. Backup và rebuild index

Dừng ứng dụng trước khi thay đổi file. Dùng SQLite backup API để snapshot nhất quán cả khi WAL đang bật:

```python
from pathlib import Path
from javis_book_intelligence.db import backup, rebuild_fts
folder = Path.home() / '.javis_book_intelligence'
backup(folder / 'library.db', Path.home() / 'javis-library-backup.db')
rebuild_fts(folder / 'library.db')
```

Khôi phục bằng cách **đóng ứng dụng**, giữ riêng bản database cũ, copy backup vào `library.db` ở `JAVIS_DATA_DIR` **cùng các file EPUB nguồn**. Kiểm tra `PRAGMA integrity_check` sau khôi phục. Nếu đổi dữ liệu gốc bên ngoài ứng dụng, chỉ mục phải rebuild.

## 5. Phạm vi kỹ thuật, hạn chế và an toàn

- Hỗ trợ EPUB 2/3 **không DRM**, XHTML được liệt kê trong OPF spine, metadata Dublin Core cơ bản. Hạn chế file upload 60 MB, giải nén tổng tối đa 220 MiB, không giải nén file tùy ý ra ổ đĩa, ngăn path traversal và ZIP bất thường. EPUB bị lỗi hoặc chế bản lạ có thể chưa xử lý.
- FTS5 index tự cập nhật bằng triggers trong **cùng transaction** với `content_units`. SQLite WAL cho phép tra cứu khi kết nối khác ghi dữ liệu đã commit. Import 1 file EPUB là một DB transaction; Milestone 2 sẽ commit từng đơn vị *chưng cất* và cho tìm ngay trong khi vẫn xử lý.
- Import trùng file dựa trên SHA-256 (trùng nội dung binary chính xác). Sách khác bản dịch/ấn bản được giữ riêng; có thể chủ động liên kết nhiều ấn bản vào cùng tác phẩm.
- Chưa có auth, quyền truy cập nhiều người, hay public hosting; chỉ dùng localhost. Người dùng chịu trách nhiệm có quyền xử lý EPUB.
- Metadata EPUB có thể thiếu/sai. Văn bản HTML được chuyển thành plain text; hình ảnh, bảng phức tạp, chú thích liên kết không được bảo toàn về bố cục ở M1.
- Không xoá EPUB đã nhập hoặc can thiệp dữ liệu cũ. Đây là ứng dụng mới, không ghi vào thư mục dự án Javis v0.1.2.

## 6. Layout / kiến trúc

```
javis_book_intelligence/
  web.py         FastAPI routes + views / JSON API
  epub.py        EPUB ZIP + OPF spine + XHTML -> units
  service.py     Import / edit metadata, dedupe SHA
  search.py      FTS5 safe queries, rank, pagination
  db.py          Connection, migrations, transaction, SQLite backup
  migrations/    0001_library.sql (M1), 0002_future_distillation_schema.sql (reserved)
  templates/     UI Jinja
  static/        CSS, browser-side debounce search
scripts/benchmark_search.py
tests/           parser, database, API, FTS, recovery-oriented tests
```

**Milestone 2 kế tiếp:** task queue bền vững, AI provider, JSON Schema, code audit, transaction publish, checkpoint/resume, API key ở env/secret store, budget; lúc đó triển khai màn hình Processing Dashboard. Trước khi quyết định tái sử dụng `book_reader.py`, `book_workflow.py`, `book_distill.py`, `book_package.py`, cần **source code plugin v0.1.2 thực tế** và checkpoint legacy để kiểm tra; hiện chưa giả định cấu trúc của chúng.
