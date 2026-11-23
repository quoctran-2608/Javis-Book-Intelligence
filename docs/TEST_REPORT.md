# Báo cáo kiểm thử Milestone 1 · 23/11/2026

## Kết quả chạy ở runtime hiện tại

- Lệnh: `PYTHONPATH=. pytest -q`.
- **18 tests passed**: migration, EPUB synthetic thực dạng ZIP/OPF/spine, SHA duplicate, nhiều edition, 3 sách cross-search, tìm keyword/phrase/prefix tiếng Việt có dấu/không dấu, tìm kiếm phân trang, chỉnh metadata và rollback, HTTP upload và download, hai file cùng lượt nhập, FTS trigger update/delete/rebuild, FTS transaction read-while-write, trạng thái future index published-only, backup/restore, input ZIP không an toàn.
- Test HTTP dùng `FastAPI TestClient`; kiểm thử localhost server thực là bước smoke riêng (xem README nếu chưa chạy ở target Windows).
- **Chưa thử** EPUB thực của người dùng, Windows runtime, API AI thật, race nhiều worker, crash `kill -9` giữa SQLite commit, khôi phục checkpoint legacy. Không tuyên bố các hạng mục này đạt.

## Benchmark synthetic 100.000 source units

- Platform: Linux 6.18.57 x86_64, CPU AMD EPYC 9V74 80-Core Processor, Python 3.13.5, SQLite 3.46.1.
- Dataset: 100.000 unit *tổng hợp, lặp lại có chủ đích*, 150 query, database khoảng **63,8 MiB**.
- Thời gian insert + cập nhật FTS: **3,87 s**.
- p50: **5,15 ms**; p95: **6,72 ms**; p99: **8,40 ms**.
- RSS đỉnh quy trình: **97,5 MiB** (bao gồm Python, index build và query).
- **Lưu ý**: Đây không phải benchmark EPUB thực, không đại diện hiệu năng thiết bị Windows, tokenizer đa ngôn ngữ hoặc khối lượng cập nhật song song kéo dài. Mục tiêu «vài trăm ms» không được coi là cam kết tổng quát.

## Nghiệm thu theo phạm vi

- **Đạt trong test local**: thư viện, metadata, SHA-256, SQLite migration, basic FTS, frontend/API, backup, index nguyên tử theo transaction.
- **Chưa nghiệm thu bằng dữ liệu thật**: import 3 EPUB thực; benchmark trên máy thực tế của người dùng; đọc nguồn có ảnh/bảng phức tạp.
- **Ngoài M1**: chưng cất bằng AI thật, audit ngữ nghĩa, tự lưu bản chưng cất từng phần, retry AI/checkpoint, Drive sync, Javis ingest. Các bảng dành cho M2 không phải bằng chứng AI chạy.
