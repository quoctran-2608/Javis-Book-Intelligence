# Rà soát sơ bộ Javis Book Distiller v0.1.2 — đọc nguồn, không can thiệp

**Nguồn đã đọc ở dạng ZIP (read-only):** `JAVIS_BOOK_DISTILLER_PLUGIN_v0.1.2_FIX_P0001_IMAGE_ONLY.zip` từ [thư mục 00_Source_and_Plugin](https://drive.google.com/drive/folders/1GY2A1D7Dfmca4_yjR0CnV_ir0Gkna8ve), kích thước 72.822 byte, SHA-256 theo Drive Manifest `41925448514b1fa76b2f724fd3f0f2bf0eceaf95a0bb8cbc2686f5d86b2cdc13`. Rà soát tĩnh mã trong ZIP, chưa đưa các hàm này vào runtime mới, chưa chạy regression test với EPUB thật và không khẳng định chúng đã hoạt động trong ứng dụng mới.

| Module cũ | Quan sát từ source thực tế | Hướng tái sử dụng | Giới hạn |
|---|---|---|---|
| `book_reader.py` | `extract_epub` (dòng 414), `extract_file` (605), `write_result` (619), `verify_result` (636); kiểm tra EPUB/DRM/ZIP, ghi `blocks.jsonl`, `source-map.json`, hỗ trợ text Markdown, ghi chú phần chỉ có ảnh | **Ưu tiên cao**: tích hợp adapter `blocks → source_blocks/content_units`, bảo toàn `block_id`, đường dẫn EPUB và checksum | Dùng `lxml`; M1 đang có parser nhẹ độc lập. Cần so sánh output trên EPUB thật trước khi chuyển hoặc phối hợp hai parser |
| `book_workflow.py` | `plan_parts` (118), `validate_source` (78), `exclusive_lock` (222), `snapshot_workspace` (519), `restore_snapshot` (555), `complete_part` (470) | **Tái sử dụng có chọn lọc**: lập kế hoạch có cấu trúc, validation, snapshot/restore | Workflow cũ phụ thuộc file `progress.json`, trạng thái `awaiting_ok`; **không** đưa nguyên gate đó sang job queue tự động của M2 |
| `book_distill.py` | `audit_part` (252), `visual_only_template` (51), `submit_part` (341), `handle_ok` (463) | **Tái sử dụng quy tắc kiểm toán nguyên văn dẫn chứng** và logic không suy đoán nội dung hình ảnh | `audit_part` chuyên Markdown/E-ID; `submit_part` yêu cầu `batch_active` và OK, không phù hợp API JSON + tự động chạy; không mang gate cũ vào M2 |
| `book_package.py` | `audit_workspace` (119), `verify_zip` (260), `pack` (349); SHA-256/manifest/ZIP audit | **Ưu tiên cao** cho xuất Markdown/ZIP và manifest ở M4 | `collect` (96) đòi `awaiting_step06_audit` và tổng hợp hoàn thành; phải tách lớp packaging độc lập với progress gate cũ |

**Kết luận:** Logic EPUB/source lineage, evidence audit và ZIP manifest là những tài sản nên giữ. Không đưa cơ chế `handle_ok`/mở batch vào M2. Không sao chép toàn bộ plugin vào M1 để tránh thêm phụ thuộc và kiến trúc file-checkpoint cũ trước khi kiểm thử tương thích.

**Dữ liệu legacy:** Manifest Drive ghi snapshot cũ ngày **09/11/2026** ở **22/763**, trong khi đặc tả người dùng mới hơn ghi **24/763**. Đây là trạng thái ở *hai thời điểm khác nhau*, không phải căn cứ sửa progress. Cần xác minh checkpoint mới nhất trực tiếp khi bắt đầu migration; không tự động mở Batch 13, không thay đổi ZIP, không ghi đè phần đã duyệt.
