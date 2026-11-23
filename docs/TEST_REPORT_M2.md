# Milestone 2 — báo cáo kiểm thử kỹ thuật

**Ngày:** 2026-11-23  
**Phiên bản:** 0.2.0  
**Môi trường:** Linux 6.18 x86_64, CPython 3.13.5, SQLite 3.46.1 (SQLite FTS5), FastAPI 0.128.2, pytest 9.0.2, Pydantic 2.13.5.  
**Lệnh:** `python -m pytest -q`  
**Kết quả:** **40 passed** (bao gồm 18 test M1 và 22 test M2), không bỏ qua/fail.

## Nhóm test M2 quan trọng

- Migrate database M1 thực tế sang M2 mà không sửa dữ liệu sách và kết quả tìm kiếm nguồn.
- Tạo run theo scope/budget/model và queue 2 unit thật từ EPUB sinh theo cấu trúc ZIP, OPF, spine; sau commit unit 1, FTS bản chưng cất truy vấn được trong khi unit 2 vẫn pending.
- JSON Schema sai hoặc dẫn chứng giả bị đánh dấu needs_review, tuyệt đối không vào `distilled_fts`.
- Retry bản lỗi: giữ revision/audit history và không sinh claim/evidence trùng; publish thành công sau khi người vận hành quyết định.
- Bounded retry HTTP 429, không retry tự động HTTP 401, pause khi cần, Stop giữ trạng thái và các bản đã commit.
- Kiểm soát budget preflight, không gọi API khi quá ngân sách; nâng budget rồi Resume.
- Quarantine source unit quá giới hạn ký tự, không cắt nguồn hoặc gửi bản thiếu cho AI.
- Atomic lease giữa hai workers/processes mô phỏng, tránh stale worker ghi hai lần, bảo đảm 1 request in-flight/run.
- Kiểm tra thay đổi nguồn khi xử lý không tạo bản chưng cất sai source.
- Tiêm lỗi SQLite đúng lúc xuất bản: rollback claims/evidence/audit/FTS; checkpoint JSON và chi phí đã ghi vẫn còn và được dùng lại mà không gọi provider lần thứ hai.
- Backup/restore, rebuild FTS, update trạng thái/chỉnh bản chưng cất không để lại chỉ mục cũ.
- HTTP endpoints và UI trên TestClient, same-origin guard, chống Host DNS rebinding.
- Mock OpenAI HTTP Responses API: cấu trúc request, `store=false`, JSON Schema strict, parse usage và response output; không đưa API key vào body.

## Benchmark tham chiếu

**Lệnh:** `python scripts/benchmark_search.py --units 10000 --queries 100`

| Chỉ số | Kết quả |
|---|---:|
| Số source units | 10.000 (nội dung tổng hợp lặp lại, không phải sách thật) |
| Số truy vấn | 100 |
| Thời gian tạo/index | 0,39 s |
| Truy vấn p50 | 1,89 ms |
| Truy vấn p95 | 2,31 ms |
| Truy vấn p99 | 3,28 ms |
| Database | 6,5 MiB |
| Process peak RSS | 97,5 MiB |
| CPU môi trường | AMD EPYC 9V74 80-Core Processor |

Benchmark này dùng bộ dữ liệu sinh tổng hợp; không chứng minh hiệu năng trên Windows hay EPUB thật lớn, và chưa benchmark nhiều tác vụ API đồng thời. Các chỉ số hoàn toàn không phản ánh chất lượng AI.

## Ngoại lệ / chưa nghiệm thu

- **Không chạy một yêu cầu OpenAI API thực** trong môi trường phát triển này vì chưa có `OPENAI_API_KEY` và mẫu EPUB được người vận hành cho phép gửi ra bên thứ ba. Test provider dùng HTTP `MockTransport`, test logic dùng `ScriptedProvider`.
- **Chưa đo semantic fidelity**: code audit chỉ kiểm tra quote có mặt nguyên văn, không bảo đảm nhận định suy ra đúng từ quote hay thiếu nội dung.
- **Chưa test Windows thực tế**: CI GitHub Actions matrix Windows/Linux được cấu hình; cần xem kết quả sau commit.
- **Không thử nghiệm khôi phục điện đột ngột trên phần cứng thật**: có test rollback transaction và recovery lease/checkpoint, không tương đương test ngắt điện vật lý.

## Kết luận

Kiểm thử **luồng kỹ thuật M2** tại môi trường nêu trên đạt; **không đồng nghĩa nghiệm thu chất lượng chưng cất thực bằng AI**. Test bằng API thực và đánh giá người dùng phải được chạy riêng theo `README.md`.
