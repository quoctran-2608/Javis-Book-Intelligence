# Milestone 2 — thiết kế thực thi và ranh giới nghiệm thu

## Giai đoạn đã hoàn tất kỹ thuật

1. **Migrations không phá dữ liệu:** `0003_incremental_engine.sql` chỉ `ALTER ADD COLUMN` + index. Bảo toàn các bảng `0001`/`0002`; chạy lại migration là idempotent.
2. **Run/job queue:** `create_run()` ghi run và jobs theo thứ tự OPF spine trong một transaction. Người dùng định rõ model, mode, số đơn vị, output language, budget, rate và max attempts. Không chạm checkpoint legacy.
3. **Provider:** `OpenAIResponsesProvider` dùng HTTPS Responses API với `store:false`, `text.format` JSON Schema strict. Env `OPENAI_API_KEY`, không lưu key. Lỗi API được phân loại retryable hay permanent; HTTP error body không ghi log.
4. **Code audit:** Pydantic strict + điều kiện không rỗng + quote chính xác là substring liền mạch của nguồn. Claim/evidence có FK liên kết `content_units`, nguồn `href` lấy từ DB (không để AI tự đặt).
5. **Three-transaction pipeline:** claim → request → persist model JSON + usage (`drafted`) → audit + claim/evidence + publish/F​TS. Chỉ `published` mới vào `distilled_fts` nhờ trigger 0002. Khi có lỗi transaction cuối, JSON response còn ở `jobs.result_json`; worker sẽ re-audit sau hết lease.
6. **Resume/retry/budget:** pending/retry_waiting/drafted/expired lease được claim trong `BEGIN IMMEDIATE`, lease token ngăn stale worker ghi. Pause/Stop không xoá đã commit. Budget preflight dùng token heuristic + output max; actual usage ghi theo provider để tính chi phí theo giá user nhập.
7. **Global search:** nguồn, chưng cất, cả hai; `source_fts`/`distilled_fts` kết hợp, snippet đánh dấu, dẫn vào trang source hoặc knowledge. Không gọi LLM cho mỗi phím.

## Vấn đề chưa thể xác nhận/kiểm thử mở rộng

- Kết nối OpenAI API thực và chất lượng AI trên sách học thuật/từ điển chưa nghiệm thu do thiếu key + sách thử có quyền API ở môi trường hiện tại; `scripts/smoke_openai.py` cho người vận hành chạy có kiểm soát.
- Điểm đúng về ngữ nghĩa, bao phủ ý chính, tính đúng quan hệ claim/quote **chưa được xác minh**: semantic audit độc lập + benchmark cần bổ sung M3.
- XHTML không tương đương mục từ từ điển; cần split/merge theo ranh giới thực, thay vì ép 1 XHTML = 1 entry.
- Trường hợp gọi API nhưng chết trước persisted response có nguy cơ tính phí lặp. Exactly-once network gọi không được bảo đảm.
- Budget chỉ là kiểm soát dự toán và hiển thị usage theo rate khai báo. Không thay thế spend limits trên hệ thống thanh toán API.
- Không thử Windows GUI trực tiếp; GitHub Actions chạy matrix Windows/Linux khi commit.

## Tiêu chí thành công phần kỹ thuật

- Một run đang xử lý unit thứ 2, search đã trả dữ liệu unit 1 vừa được code audit + commit.
- Response chưa qua audit hoặc quote sai phải vào needs_review, không được index.
- Transaction publish nổ phải rollback toàn bộ claim/evidence/audit/FTS, giữ response checkpoint và usage.
- Lease cũ không được ghi đè bản mới hoặc thu phí trong DB hai lần; khôi phục draft không gọi lại API.
- `pause`, `stop`, `resume`, `retry`, `budget preflight` và trang dashboard hoạt động qua HTTP.
- Backup/restore giữ cả source, revision, job, FTS và toàn vẹn khóa ngoại.

**Nghiệm thu cuối:** chỉ tuyên bố chất lượng model đạt sau chạy API thực có mẫu từ sách thường và từ điển, có bộ golden claim/evidence và người kiểm tra. 
