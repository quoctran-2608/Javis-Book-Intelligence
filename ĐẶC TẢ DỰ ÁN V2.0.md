# ĐẶC TẢ DỰ ÁN V2.0
# JAVIS BOOK INTELLIGENCE
### Automated Book Distillation · Digital Library Management · Instant Knowledge Search

**Tên sản phẩm:** Javis Book Intelligence

**Tên bộ máy chưng cất:** Javis Book Distiller AUTO

**Phiên bản đầu tiên:** MVP v1.0

**Hệ sinh thái đích:** Javis Second Brain

**Yêu cầu nền tảng:** Python, EPUB, AI API/Local, SQLite, Full-Text Search, Google Drive.

**Mục tiêu:** Xây dựng một ứng dụng thực sự, hoạt động tự động, giúp quản lý thư viện sách điện tử, đọc hiểu và chưng cất nội dung bằng AI, lưu trữ tri thức có cấu trúc vào database, rồi cho phép tìm kiếm nhanh trên toàn bộ thư viện.

---

# I. TẦM NHÌN VÀ MỤC TIÊU

Tôi muốn xây dựng một hệ thống thư viện tri thức cá nhân phục vụ Javis Second Brain.

Ứng dụng không chỉ dùng để xử lý từ điển Phật học mà phải hỗ trợ **mọi loại sách EPUB thông thường**, chẳng hạn:

- Sách khoa học, học thuật, giáo trình.
- Sách y học, sức khỏe, chuyên ngành.
- Sách lịch sử, triết học, tôn giáo.
- Sách kinh doanh, quản trị, công nghệ.
- Sách văn học, tiểu thuyết.
- Sách tham khảo, bách khoa toàn thư, từ điển.

Mỗi loại sách cần được xử lý theo cấu trúc và bản chất nội dung của nó.

Ứng dụng phải cho phép người dùng nhập một hoặc nhiều EPUB, quản lý thông tin sách, tự động chưng cất nội dung bằng AI và lưu kết quả liên tục vào database.

Đặc biệt:

**Ngay khi một đoạn/chương/mục từ chưng cất thành công, nó phải được lưu và lập chỉ mục, cho phép tìm kiếm ngay mà không cần đợi xử lý xong toàn bộ sách.**

Sau khi xây dựng được thư viện tri thức, tôi muốn gõ bất kỳ từ khóa, thuật ngữ, cụm từ, câu văn hoặc đoạn văn nào vào ô tìm kiếm để tìm thông tin liên quan trên tất cả các sách đã nhập.

Mục tiêu dài hạn là biến ứng dụng thành một công cụ quản lý và tra cứu tri thức cá nhân thực sự, không chỉ là phần mềm chuyển đổi EPUB sang Markdown.

---

# II. BA MODULE CHÍNH

## Module A — Book Library Manager

Quản lý thông tin và danh mục sách.

## Module B — Book Distiller Engine

Tự động đọc hiểu, chưng cất, kiểm toán và lưu kiến thức bằng Python kết hợp AI.

## Module C — Knowledge Search Engine

Tìm kiếm nhanh trên toàn bộ tri thức đã lưu trong database.

Ba module phải được thiết kế độc lập về chức năng nhưng sử dụng chung cơ sở dữ liệu và hệ thống định danh.

---

# III. MODULE A — BOOK LIBRARY MANAGER

## 1. Nhập sách

Người dùng có thể:

- Chọn và tải lên EPUB.
- Nhập nhiều sách cùng lúc.
- Kéo thả file.
- Xem sách đã nhập.
- Tự động trích xuất metadata từ EPUB.
- Chỉnh sửa hoặc bổ sung metadata.
- Phát hiện file trùng bằng SHA-256.
- Quyết định cách xử lý khi một sách đã tồn tại.

Không ghi đè sách cũ hoặc kết quả chưng cất cũ mà không có cơ chế kiểm soát.

MVP ưu tiên EPUB không có DRM. PDF, OCR và các định dạng khác là giai đoạn mở rộng, không phải điều kiện bắt buộc của MVP.

## 2. Hồ sơ thông tin sách

Mỗi sách có một hồ sơ gồm:

| Nhóm | Trường thông tin |
|---|---|
| Nhận dạng | Book ID, tên sách, phụ đề |
| Tác giả | Một hoặc nhiều tác giả |
| Đóng góp | Người dịch, biên tập, hiệu đính |
| Xuất bản | Nhà xuất bản, năm xuất bản, ISBN |
| Phiên bản | Lần xuất bản, bản dịch, phiên bản điện tử |
| Phân loại | Thể loại, chủ đề, thẻ tag |
| Ngôn ngữ | Ngôn ngữ gốc, ngôn ngữ bản dịch |
| Mô tả | Tóm tắt sách, ghi chú cá nhân |
| File | Tên EPUB, dung lượng, SHA-256 |
| Trạng thái | Chưa xử lý, đang xử lý, hoàn thành, cần kiểm tra |
| Thống kê | Số chương, số đơn vị tri thức, số lỗi, tiến độ |
| Hệ thống | Ngày thêm, ngày cập nhật, ngày xử lý |

Metadata nên được trích xuất tự động từ EPUB khi có thể, nhưng không giả định metadata luôn đầy đủ hoặc chính xác.

Cho phép người dùng chỉnh sửa trực tiếp trên giao diện.

Lưu phân biệt dữ liệu trích xuất từ EPUB và dữ liệu được người dùng hiệu chỉnh.

## 3. Quản lý phiên bản sách

Phải phân biệt:

- **Book/Work:** Tác phẩm ở mức khái niệm.
- **Edition:** Ấn bản, bản dịch hoặc lần xuất bản cụ thể.
- **Source File:** File EPUB thực tế.
- **Processing Run:** Lần xử lý bằng một cấu hình AI nhất định.

Ví dụ, cùng một tác phẩm có bản tiếng Anh và tiếng Việt thì không được coi hai file là một nội dung giống hệt.

Nếu người dùng chạy lại cùng sách bằng model khác, hệ thống phải có khả năng lưu bản kết quả mới hoặc lịch sử revision mà không phá hủy bản đã được phê duyệt.

## 4. Quản lý danh mục

Giao diện thư viện cần hỗ trợ:

- Danh sách sách dạng bảng hoặc card.
- Tìm sách theo tên, tác giả, thể loại.
- Lọc theo ngôn ngữ.
- Lọc theo trạng thái chưng cất.
- Sắp xếp theo ngày thêm, tiến độ, tên sách.
- Xem chi tiết một sách.
- Xem mục lục.
- Xem các phần đã xử lý.
- Xem lỗi và lịch sử xử lý.
- Chỉnh sửa tag và metadata.

MVP không cần các chức năng quản lý thư viện quá phức tạp như mượn/trả sách, quản lý người dùng doanh nghiệp hoặc marketplace.

---

# IV. MODULE B — BOOK DISTILLER ENGINE

## 1. Nguyên tắc vận hành

**Code quản lý quy trình; AI thực hiện đọc hiểu và suy luận.**

Python đảm nhiệm:

- Đọc EPUB.
- Trích xuất cấu trúc nguồn.
- Tạo mã định danh.
- Phân chia công việc.
- Điều phối hàng đợi.
- Gọi AI API/local.
- Kiểm tra dữ liệu.
- Lưu database.
- Lập chỉ mục tìm kiếm.
- Quản lý checkpoint.
- Retry khi lỗi.
- Báo cáo tiến độ.
- Xuất và đồng bộ dữ liệu.

AI đảm nhiệm:

- Hiểu nội dung.
- Nhận diện ý quan trọng.
- Chưng cất kiến thức.
- Giải thích thuật ngữ.
- Phân biệt quan điểm và ngoại lệ.
- Đề xuất quan hệ khái niệm.
- Đánh giá sự phù hợp giữa bản chưng cất và nguồn.

## 2. Hỗ trợ nhiều thể loại sách

Ứng dụng phải có chiến lược xử lý phù hợp với từng loại sách.

### Dictionary Mode

Dành cho từ điển và bách khoa.

Đơn vị chính là mục từ hoàn chỉnh.

Bản chưng cất cần giữ định nghĩa, biến thể thuật ngữ, ví dụ, danh mục và các tham chiếu.

### General Book Mode

Dành cho sách thông thường.

Đơn vị xử lý dựa trên chương, tiểu mục hoặc đoạn có tính hoàn chỉnh về lập luận.

Phải giữ mối liên hệ giữa các chương và tránh tóm tắt những đoạn bị cắt giữa ý.

### Academic Mode

Dành cho giáo trình, tài liệu nghiên cứu, sách chuyên ngành.

Chú trọng:

- Định nghĩa.
- Luận điểm.
- Phương pháp.
- Bằng chứng.
- Số liệu.
- Công thức.
- Ngoại lệ.
- Giới hạn nghiên cứu.
- Nguồn trích dẫn.

### Narrative Mode

Dành cho tiểu thuyết, truyện hoặc sách có diễn tiến kể chuyện.

Phải giữ được bối cảnh, diễn tiến, nhân vật, sự kiện và quan hệ nhân quả mà không biến cốt truyện thành những nhận định thiếu ngữ cảnh.

Các chế độ này dùng chung bộ máy nhưng có chiến lược phân đoạn và prompt riêng.

MVP có thể bắt đầu bằng General Book Mode và Dictionary Mode. Các chế độ khác được bổ sung sau khi hai chế độ đầu đạt kiểm thử.

## 3. Quy trình chưng cất tự động

Quy trình mục tiêu:

1. Nhập EPUB và tạo hồ sơ sách.
2. Trích xuất nội dung và metadata.
3. Phân tích cấu trúc sách.
4. Tạo các đơn vị nội dung cần chưng cất.
5. Ghi các tác vụ vào database.
6. Tự động gọi AI theo hàng đợi.
7. Nhận JSON có cấu trúc từ AI.
8. Kiểm toán bằng code.
9. Kiểm toán ngữ nghĩa bằng AI theo chính sách chất lượng.
10. Sửa hoặc retry khi cần.
11. Lưu phiên bản đạt yêu cầu vào database.
12. Cập nhật chỉ mục tìm kiếm.
13. Lưu checkpoint.
14. Tiếp tục đơn vị kế tiếp.
15. Khi hoàn tất, lập chỉ mục/tổng hợp toàn sách.
16. Xuất bản gói dữ liệu và đồng bộ Google Drive.

**Không cần người dùng nhập OK liên tục.**

Người dùng cấp phép một lượt chạy với phạm vi và ngân sách được xác định trước.

---

# V. YÊU CẦU BẮT BUỘC: LƯU DỮ LIỆU NGAY KHI CHƯNG CẤT

Đây là một trong những chức năng quan trọng nhất.

Không được xây quy trình theo kiểu xử lý xong cả cuốn sách mới đưa kết quả vào database.

Thay vào đó:

**Mỗi đơn vị kiến thức hoàn thành phải được lưu ngay lập tức.**

Ví dụ:

Ứng dụng đang xử lý cuốn sách có 100 chương.

Sau khi hoàn thành chương 1, hệ thống ghi nội dung chưng cất của chương 1 vào database và lập chỉ mục tìm kiếm.

Khi đang xử lý chương 2, người dùng đã có thể tìm kiếm nội dung của chương 1.

Tương tự, khi chương 50 đang xử lý, toàn bộ phần đã hoàn thành từ chương 1 đến chương 49 vẫn phải tìm kiếm được bình thường.

## Yêu cầu kỹ thuật

- Lưu tác vụ trước khi gọi AI.
- Lưu bản nháp theo trạng thái.
- Chỉ công bố vào chỉ mục chính khi đạt điều kiện chất lượng.
- Sử dụng database transaction để lưu kết quả và cập nhật chỉ mục nhất quán.
- Có thể giữ các bản chưa đạt ở khu vực kiểm tra riêng.
- Không đánh dấu hoàn thành nếu chỉ ghi được một phần dữ liệu.
- Retry không được sinh bản ghi trùng.
- Khi sửa bản chưng cất, chỉ mục phải được cập nhật tương ứng.
- Cho phép xây dựng lại chỉ mục tìm kiếm từ dữ liệu gốc trong database.

Database là nguồn dữ liệu chính của ứng dụng. Markdown/ZIP là các dạng xuất bản hoặc trao đổi dữ liệu, không phải nơi duy nhất chứa tri thức.

---

# VI. MODULE C — KNOWLEDGE SEARCH ENGINE

## 1. Mục tiêu

Ứng dụng cần có một ô tìm kiếm chung cho toàn bộ thư viện.

Người dùng có thể gõ:

- Một từ.
- Một thuật ngữ.
- Một tên riêng.
- Một cụm từ.
- Một câu.
- Một đoạn văn.
- Một câu hỏi tự nhiên.

Kết quả tìm kiếm phải cho biết thông tin đó xuất hiện trong sách nào, ở đơn vị tri thức nào và liên quan đến nội dung nào.

Không yêu cầu người dùng nhớ tên sách trước khi tìm kiếm.

## 2. Các chế độ tìm kiếm

### A. Keyword Search — bắt buộc trong MVP

Tìm theo từ khóa, thuật ngữ, tiêu đề và nội dung chưng cất.

Ví dụ: `abhidharma`, `vô thường`, `thiền định`.

Kết quả xếp theo mức độ liên quan.

### B. Phrase Search — bắt buộc trong MVP

Tìm một cụm từ hoặc đoạn văn có nội dung khớp trong dữ liệu được lập chỉ mục.

Hỗ trợ tìm trong:

- Nội dung chưng cất.
- Tiêu đề.
- Thuật ngữ.
- Dẫn chứng.
- Nội dung nguồn đã được phép lập chỉ mục.

Cần phân biệt tìm đúng cụm từ với tìm nội dung tương tự.

### C. Prefix / Partial Search — ưu tiên trong MVP

Gõ một phần từ hoặc cụm từ để nhận kết quả gợi ý.

Tìm chuỗi con tùy chọn nếu chỉ mục hỗ trợ.

Cần xử lý việc gõ tiếng Việt có dấu, không dấu và ký tự Unicode.

### D. Semantic Search — giai đoạn nâng cấp

Người dùng nhập một câu hoặc đoạn mô tả ý tưởng.

Hệ thống tìm những đơn vị tri thức gần nghĩa dù không chứa cùng từ ngữ.

Sử dụng embeddings và vector search.

Không được tuyên bố semantic search là phép tìm chính xác tuyệt đối.

### E. Hybrid Search — giai đoạn nâng cấp

Kết hợp full-text search và semantic search để xếp hạng kết quả.

Hệ thống có thể ưu tiên kết quả khớp chính xác trước, sau đó bổ sung kết quả tương đồng ngữ nghĩa.

## 3. Yêu cầu tìm kiếm instant

Tôi muốn tìm kiếm cảm giác gần như tức thì.

Đề xuất kỹ thuật ban đầu:

- SQLite FTS5.
- Lập chỉ mục tăng dần.
- Tìm kiếm có xếp hạng.
- Trả kết quả giới hạn và phân trang.
- Debounce khoảng 150–250 ms khi người dùng đang gõ.
- Sử dụng cache thích hợp.
- Không gọi LLM cho mỗi lần gõ phím.

Mục tiêu thử nghiệm cho MVP là thời gian truy vấn full-text ở mức vài trăm mili giây trên một thư viện mẫu khoảng 100.000 đơn vị nội dung, với máy và khối lượng dữ liệu được ghi rõ.

Đây là mục tiêu benchmark, không phải cam kết hiệu năng cho mọi máy hoặc mọi truy vấn.

Semantic search có thể hoạt động khi người dùng nhấn Enter hoặc chọn chế độ tìm theo ý nghĩa.

## 4. Kết quả tìm kiếm phải hữu ích

Mỗi kết quả nên hiển thị:

- Tiêu đề đoạn kiến thức.
- Đoạn trích phù hợp có highlight.
- Tên sách.
- Tác giả.
- Chương hoặc mục từ.
- Thể loại sách.
- Ngôn ngữ.
- Trạng thái kiểm toán.
- Vị trí trong nguồn.
- Điểm xếp hạng phù hợp.

Khi bấm vào kết quả, người dùng mở trang chi tiết và xem:

1. Nội dung đã chưng cất.
2. Các nhận định.
3. Dẫn chứng.
4. Vị trí trong EPUB.
5. Các mục kiến thức liên quan.
6. Thông tin sách và ấn bản.

Nếu có thể, cung cấp chức năng chuyển đến vị trí tương ứng trong EPUB gốc. Phải kiểm thử độ chính xác của đường dẫn, vì không phải mọi EPUB đều có định vị ổn định như số trang sách in.

## 5. Bộ lọc tìm kiếm

Cho phép lọc theo:

- Sách.
- Tác giả.
- Thể loại.
- Chủ đề/tag.
- Ngôn ngữ.
- Năm xuất bản.
- Trạng thái chưng cất.
- Trạng thái kiểm toán.
- Mục từ/chương.
- Loại dữ liệu: nguồn gốc hoặc bản chưng cất.

## 6. Tìm kiếm xuyên sách

Một thuật ngữ có thể xuất hiện trong 20 cuốn sách.

Ứng dụng phải hiển thị kết quả từ nhiều sách, giúp người dùng xem các cách trình bày khác nhau của cùng khái niệm.

Không tự gộp các định nghĩa có khác biệt thành một định nghĩa duy nhất.

Có thể đề xuất nhóm kết quả theo chủ đề hoặc thuật ngữ, nhưng vẫn giữ nguồn gốc từng kết quả.

## 7. Giới hạn cần minh bạch

Không thể bảo đảm mọi từ hoặc đoạn được nhập đều có kết quả.

Nếu người dùng tìm một cụm từ chỉ có trong EPUB gốc nhưng không được giữ trong bản chưng cất, kết quả có thể không xuất hiện trong chế độ tìm kiếm bản chưng cất.

Để giải quyết, hệ thống nên có hai phạm vi:

- **Search Distilled Knowledge:** Tìm trong tri thức đã chưng cất.
- **Search Original Source:** Tìm trong văn bản nguồn đã trích xuất, khi dữ liệu nguồn có sẵn.

Cần hiển thị rõ kết quả đến từ nguồn nào.

Không được trình bày nội dung AI diễn giải như trích dẫn nguyên văn tác giả.

---

# VII. THIẾT KẾ DATABASE

Ưu tiên **SQLite + FTS5** cho MVP chạy trên máy cá nhân.

Chỉ cân nhắc PostgreSQL, Meilisearch hoặc bộ máy tìm kiếm chuyên dụng khi benchmark chứng minh SQLite không đáp ứng được quy mô thực tế.

Các nhóm bảng đề xuất:

| Bảng | Vai trò |
|---|---|
| `books` | Tác phẩm và thông tin nhận dạng |
| `editions` | Ấn bản, bản dịch và lần xuất bản |
| `contributors` | Tác giả, dịch giả, biên tập viên |
| `book_contributors` | Liên kết sách với người đóng góp |
| `categories` / `tags` | Phân loại và chủ đề |
| `source_files` | EPUB gốc, SHA-256 và thông tin file |
| `source_blocks` | Nội dung nguồn cùng vị trí và mã định danh |
| `content_units` | Chương, tiểu mục, mục từ hoặc đơn vị xử lý |
| `processing_runs` | Các lần xử lý và cấu hình AI |
| `jobs` | Hàng đợi và trạng thái tác vụ |
| `distilled_units` | Đơn vị tri thức đã chưng cất |
| `distilled_revisions` | Các phiên bản sửa đổi |
| `claims` | Nhận định có cấu trúc |
| `evidence` | Dẫn chứng liên kết với nguồn |
| `knowledge_links` | Quan hệ giữa các đơn vị kiến thức |
| `audit_results` | Kết quả kiểm toán |
| `search_index` | Chỉ mục toàn văn FTS5 |
| `sync_jobs` | Hàng đợi đồng bộ Google Drive |

Embeddings và vector index có thể là các bảng hoặc thành phần tùy chọn trong giai đoạn sau.

## Các nguyên tắc dữ liệu

1. Mỗi bản ghi có ID ổn định.
2. Có foreign key và ràng buộc toàn vẹn.
3. Giữ phân biệt sách, phiên bản và file EPUB.
4. Không xóa nguồn khi cập nhật bản chưng cất.
5. Mỗi kết quả có thể truy về nguồn.
6. Lưu model, prompt version, processing run và ngày tạo khi cần.
7. Lưu lịch sử sửa đổi.
8. Tránh duplicate bằng khóa duy nhất và cơ chế idempotency.
9. Sử dụng migration có phiên bản cho schema database.
10. Chỉ mục FTS phải có thể tạo lại từ dữ liệu chính.

Cần thiết kế cách chuẩn hóa Unicode và dấu tiếng Việt, nhưng không được chuẩn hóa đến mức làm sai thuật ngữ chuyên môn.

---

# VIII. AI ENGINE

Ứng dụng hỗ trợ nhiều backend.

### OpenAI API

Dùng để chưng cất và kiểm toán khi được cấu hình.

### Anthropic Claude API

Có thể thay thế hoặc kiểm tra chéo.

### Ollama / Local AI

Cho phép chạy model cục bộ.

### Hybrid Mode

Cho phép lựa chọn model theo nhiệm vụ.

Ví dụ:

- Local AI thực hiện phân loại đơn giản.
- Model API mạnh xử lý sách học thuật hoặc nội dung khó.
- AI khác thực hiện kiểm toán ngữ nghĩa.
- Python thực hiện tất cả phép kiểm tra xác định được bằng code.

Không mặc định model local nhỏ có chất lượng bằng model API mạnh.

Phải có benchmark để quyết định.

ChatGPT/Claude subscription không được mặc định xem như API miễn phí không giới hạn. Chỉ sử dụng các phương thức tích hợp chính thức được nhà cung cấp cho phép.

## Cấu hình AI

Cho phép người dùng chỉnh:

- Backend.
- Model.
- API key.
- Endpoint.
- Token budget.
- Context limit.
- Concurrency.
- Retry.
- Timeout.
- Ngân sách.
- Model chưng cất.
- Model kiểm toán.
- Ngôn ngữ đầu ra.

Khóa API và dữ liệu nhạy cảm không được đưa vào log, file Markdown hoặc ZIP.

---

# IX. KIỂM TOÁN CHẤT LƯỢNG

Cần hai lớp kiểm toán.

## 1. Code Audit

Kiểm tra:

- JSON Schema.
- Đầy đủ ID.
- Định dạng đúng.
- Nguyên văn dẫn chứng.
- Vị trí nguồn.
- Không trùng ID.
- Không thiếu block được giao.
- Checksum.
- Trạng thái hợp lệ.
- Quan hệ dữ liệu nhất quán.

## 2. Semantic Audit

AI rà soát:

- Bỏ sót ý quan trọng.
- Hiểu sai định nghĩa.
- Dịch sai thuật ngữ.
- Sai niên đại hoặc số liệu.
- Nhầm chủ thể.
- Gộp các quan điểm khác nhau.
- Tạo kết luận không có nguồn.
- Bỏ qua ngoại lệ.

Nếu lỗi có thể sửa, thử sửa có kiểm soát.

Nếu không đạt sau số lần cho phép, đánh dấu `needs_review`.

Không được dùng điểm tự tin của model như chứng nhận độc lập.

Cần phân biệt kết quả mới xử lý, đã đạt audit tự động và đã được con người kiểm tra.

---

# X. CHECKPOINT VÀ XỬ LÝ TỰ ĐỘNG

Hệ thống cần có hàng đợi công việc bền vững.

Các trạng thái có thể gồm:

`pending`, `processing`, `drafted`, `auditing`, `completed`, `needs_review`, `retry_waiting`, `failed`.

Yêu cầu:

- Chạy liên tục.
- Không cần OK sau mỗi phần.
- Pause/resume.
- Dừng khẩn cấp.
- Tự tiếp tục sau lỗi.
- Retry có giới hạn.
- Không ghi kết quả trùng.
- Không mất phần đã hoàn thành.
- Có log lỗi.
- Có giới hạn ngân sách.
- Có checkpoint.
- Có chức năng backup và restore database.

Đặc biệt phải kiểm thử trường hợp ứng dụng bị tắt giữa lúc ghi dữ liệu hoặc đồng bộ Drive.

Không coi việc gửi dữ liệu tới AI thành công đồng nghĩa tác vụ đã hoàn thành.

---

# XI. GIAO DIỆN NGƯỜI DÙNG

MVP cần tối thiểu năm màn hình.

## 1. Library

Quản lý sách và metadata.

Có chức năng thêm EPUB, lọc, tìm, sửa thông tin và xem tiến độ.

## 2. Book Detail

Hiển thị thông tin sách, mục lục, số phần xử lý, trạng thái, danh sách tri thức và lịch sử xử lý.

## 3. Processing Dashboard

Hiển thị tiến độ trực tiếp, hàng đợi, model đang chạy, số token, chi phí, lỗi, nút Start/Pause/Resume/Stop.

## 4. Global Search

Đây là màn hình quan trọng.

Phải có ô tìm kiếm toàn thư viện, kết quả có highlight, bộ lọc và đường dẫn đến tri thức gốc.

Phải tìm được các phần đã xử lý ngay khi một sách vẫn đang chạy.

## 5. Knowledge Detail

Hiển thị một đơn vị tri thức, dẫn chứng, nguồn gốc, quan hệ kiến thức, lịch sử sửa và trạng thái audit.

Giao diện nên đơn giản, dễ thao tác với người không chuyên lập trình.

---

# XII. GOOGLE DRIVE VÀ JAVIS SECOND BRAIN

Đã có thư mục Google Drive của dự án cũ:

https://drive.google.com/drive/folders/150wCF0XjM8ByYJ2A_Y89EBYaoqNGWvJJ

Ứng dụng mới cần đồng bộ có kiểm soát:

- Checkpoint.
- Database backup.
- Báo cáo.
- Markdown.
- ZIP.
- Manifest.
- Các file cấu hình được phép sao lưu.

Không đồng bộ API key hoặc dữ liệu nhạy cảm.

Không nên dùng Google Drive làm cơ sở dữ liệu đang được ghi trực tiếp, vì dễ phát sinh lỗi đồng bộ và xung đột.

Nên lưu database trên ổ đĩa local, backup bằng cơ chế nhất quán, rồi đồng bộ bản backup và các sản phẩm ra Drive.

Javis Second Brain vẫn là hệ thống đích.

Ứng dụng phải xuất được dữ liệu tri thức có định dạng và metadata phù hợp để có thể ingest vào Javis.

Chỉ tuyên bố ingest thành công sau khi kiểm thử trên runtime Javis thật.

---

# XIII. TÁI SỬ DỤNG JAVIS BOOK DISTILLER v0.1.2

Chúng tôi đã có plugin Javis Book Distiller v0.1.2.

Các thành phần được biết đến gồm:

- `book_reader.py`
- `book_workflow.py`
- `book_distill.py`
- `book_package.py`

Cần đọc source code thực tế trước khi quyết định tái sử dụng hoặc sửa đổi.

Không viết lại các thành phần đã hoạt động tốt nếu không cần thiết.

## Checkpoint hiện có

Sách: *The Princeton Dictionary of Buddhism*.

Tiến độ: 24/763 phần hoàn thành.

Checkpoint mới nhất:

https://drive.google.com/file/d/1-BVM90yLH1P0uH01uB_V71bfef561qIr/view?usp=drivesdk

Cần hỗ trợ import checkpoint cũ và chuyển dữ liệu sang database mới.

Không được giả định 24 part cũ tương đương 24 mục từ hoàn chỉnh.

Phải giữ nguồn, nội dung đã chưng cất, lịch sử và trạng thái kiểm toán.

Kết quả cũ có thể được đánh dấu `legacy_imported`, sau đó người dùng quyết định có cần tái xử lý hay không.

Không tự sửa file progress cũ để vượt cơ chế OK.

---

# XIV. STACK CÔNG NGHỆ MVP

Tôi muốn chọn giải pháp **dễ xây dựng, ít thành phần phụ thuộc, dễ bảo trì**.

Đề xuất mặc định:

| Thành phần | Công nghệ |
|---|---|
| Ngôn ngữ | Python |
| EPUB parser | Tái sử dụng Javis reader, có thể dùng EbookLib |
| Giao diện/API | FastAPI + giao diện web đơn giản, hoặc Streamlit nếu có lý do tốt |
| Database | SQLite |
| Tìm kiếm | SQLite FTS5 |
| Schema dữ liệu | Pydantic |
| Task queue | Hàng đợi bền vững dựa trên SQLite cho MVP |
| AI đầu tiên | OpenAI API |
| AI mở rộng | Claude API, Ollama |
| Backup | SQLite backup an toàn + ZIP/manifest |
| Đồng bộ | Google Drive API |
| Kiểm thử | pytest |
| Phân phối | ZIP ứng dụng, script cài đặt và hướng dẫn chạy |

Ưu tiên bản chạy trên máy Windows thông qua localhost trong trình duyệt, nhưng kiến trúc nên có khả năng chạy Linux/server.

Chưa chọn cấu hình AI local cuối cùng khi chưa biết CPU/GPU/VRAM của máy.

Không triển khai Docker, Redis, Celery, PostgreSQL, Kubernetes hoặc microservices nếu MVP chưa cần.

---

# XV. PHẠM VI MVP VÀ PHẦN MỞ RỘNG

## Phải có trong MVP v1.0

- Nhập EPUB.
- Tạo và chỉnh sửa hồ sơ sách.
- Quản lý tác giả, thể loại, phiên bản cơ bản.
- Nhận diện sách trùng.
- Phân đoạn theo chương hoặc mục từ.
- Chưng cất bằng ít nhất một AI API.
- Lưu liên tục vào SQLite.
- Audit bằng code.
- Tìm kiếm toàn văn FTS5.
- Tìm kiếm trong khi xử lý.
- Hiển thị kết quả theo sách/chương.
- Pause/resume.
- Retry lỗi.
- Checkpoint.
- Xuất Markdown/ZIP.
- Bộ test tự động.
- Hướng dẫn cài đặt và sử dụng.

## Nên bổ sung trong v1.1

- Semantic audit tự động.
- Tối ưu chất lượng nhiều loại sách.
- Import checkpoint legacy hoàn chỉnh.
- Google Drive đồng bộ tự động.
- Quản lý revision.
- Báo cáo chi phí và chất lượng nâng cao.
- Tìm kiếm chuỗi con và chuẩn hóa thuật ngữ đa ngôn ngữ tốt hơn.

## Có thể bổ sung từ v1.2 trở đi

- Semantic/vector search.
- Hybrid search.
- Claude/Ollama.
- Tạo chỉ mục chủ đề xuyên sách.
- Liên kết tri thức tự động.
- Hỗ trợ nhiều worker/máy.
- PDF/OCR/vision nâng cao.
- Các hình thức RAG hỏi đáp trên thư viện.

Thứ tự có thể thay đổi theo kết quả thử nghiệm thực tế.

**Không trì hoãn chức năng tìm kiếm cơ bản để chờ semantic search hoặc AI local.**

---

# XVI. TIÊU CHÍ NGHIỆM THU MỚI

MVP phải vượt qua các bài kiểm tra thực tế sau.

### Test 1 — Quản lý thư viện

Nhập ba EPUB khác nhau.

Trích xuất metadata và cho phép sửa tên, tác giả, thể loại, phiên bản.

Phân biệt file trùng với hai ấn bản khác nhau của cùng tác phẩm.

### Test 2 — Chưng cất thực

Dùng AI API thực để xử lý một phần của sách thường và một phần của từ điển.

Không sử dụng fixture giả để tuyên bố chất lượng AI đã đạt.

### Test 3 — Lưu tức thời

Bắt đầu chưng cất một cuốn EPUB.

Ngay sau khi đơn vị đầu tiên hoàn thành audit, kiểm tra nó đã có trong database và chỉ mục FTS.

### Test 4 — Tìm kiếm khi đang convert

Trong lúc hệ thống tiếp tục chưng cất, nhập từ khóa thuộc đơn vị đã hoàn thành.

Kết quả phải xuất hiện mà không cần dừng tác vụ hoặc chờ hoàn thành toàn sách.

### Test 5 — Tìm kiếm xuyên sách

Sau khi có dữ liệu từ ít nhất ba sách, nhập một thuật ngữ xuất hiện trong nhiều sách.

Hệ thống phải trả kết quả từ đúng các sách chứa dữ liệu liên quan.

### Test 6 — Tìm kiếm cụm từ

Nhập một câu hoặc cụm từ có trong nội dung được lập chỉ mục.

Kết quả phải xác định được đơn vị chứa nội dung đó.

Phải phân biệt kết quả tìm đúng chữ với kết quả gần nghĩa.

### Test 7 — Khả năng phục hồi

Đang xử lý thì tắt ứng dụng.

Khởi động lại.

Các đơn vị đã commit phải còn nguyên, các tác vụ dở dang được khôi phục an toàn, không có bản hoàn thành giả.

### Test 8 — Sửa và cập nhật chỉ mục

Sửa một bản chưng cất theo quy trình cho phép.

Hệ thống phải cập nhật kết quả tìm kiếm tương ứng mà không để lại bản cũ trong chỉ mục hiện hành.

### Test 9 — Hiệu năng

Tạo bộ dữ liệu benchmark lớn bằng nội dung thử nghiệm hợp lệ.

Đo thời gian truy vấn FTS, mức sử dụng bộ nhớ và tác động của việc ghi dữ liệu song song với tìm kiếm.

Ghi rõ phần cứng, số bản ghi, kích thước dữ liệu và phân vị thời gian đáp ứng.

### Test 10 — Tính toàn vẹn

Kiểm tra database, các khóa ngoại, trạng thái tác vụ, dẫn chứng, manifest và backup/restore.

Không được đánh dấu hoàn thành khi kiểm toán hoặc transaction thất bại.

---

# XVII. RỦI RO PHẢI XỬ LÝ

1. **Metadata EPUB thiếu hoặc sai:** phải cho phép hiệu chỉnh, lưu nguồn gốc giá trị.
2. **Một mục từ trải dài nhiều block:** phải ghép theo cấu trúc trước khi AI chưng cất.
3. **Bản chưng cất bỏ sót ý:** cần benchmark và semantic audit.
4. **Dẫn chứng đúng chữ nhưng sai ngữ cảnh:** kiểm toán code không thay thế kiểm toán ngữ nghĩa.
5. **Quá nhiều bản ghi:** cần index, pagination và đo hiệu năng thực.
6. **Xung đột khi nhiều worker ghi SQLite:** cần điều phối ghi phù hợp và transaction ngắn.
7. **Thay model hoặc prompt:** phải lưu phiên bản xử lý, không ghi đè âm thầm.
8. **Tìm kiếm tiếng Việt và đa ngôn ngữ:** cần kiểm thử tokenizer, dấu, Unicode và các kiểu phiên âm.
9. **Google Drive mất kết nối:** queue đồng bộ phải retry độc lập.
10. **Bản quyền sách:** hệ thống phải được thiết kế cho nội dung người dùng có quyền xử lý, chú trọng lưu trữ cá nhân, kiểm soát quyền truy cập và tránh công khai nguyên văn sách trái phép.
11. **Chi phí API:** giới hạn ngân sách, token, concurrency và retry.
12. **AI hallucination:** mọi nhận định quan trọng phải có truy xuất nguồn, và mục không chắc chắn phải được đánh dấu.

---

# XVIII. LỘ TRÌNH XÂY DỰNG ĐỀ XUẤT

## Milestone 1 — Library + Database + Search

Đây là bước tôi muốn ưu tiên.

Xây ứng dụng có thể nhập EPUB, tạo hồ sơ sách, trích xuất nội dung, lưu database và tìm kiếm toàn văn trên dữ liệu trích xuất.

Mục đích là chứng minh nền tảng quản lý thư viện và tìm kiếm hoạt động thực sự, trước khi thêm bộ AI tự động phức tạp.

## Milestone 2 — AI Distillation + Incremental Save

Kết nối AI API.

Chưng cất từng đơn vị, lưu database ngay khi hoàn thành và cập nhật tìm kiếm.

Có checkpoint và các trạng thái tác vụ.

## Milestone 3 — Quality + Recovery

Bổ sung audit, retry, xử lý lỗi, resume, quản lý phiên bản và benchmark chất lượng.

## Milestone 4 — Legacy Migration + Javis Export

Import checkpoint Javis Book Distiller v0.1.2.

Giữ dữ liệu đã làm.

Xuất Markdown/ZIP và kiểm thử gói bàn giao.

## Milestone 5 — Google Drive + Advanced AI/Search

Đồng bộ Drive.

Bổ sung Claude, local AI, semantic search và các tính năng nâng cao tùy theo nhu cầu thực tế.

---

# XIX. CÁCH TÔI MUỐN CHATGPT TRIỂN KHAI

Bạn hãy đóng vai:

- Software Architect.
- Senior Python Developer.
- Database Engineer.
- Search Engineer.
- AI/LLM Engineer.
- QA Engineer.

Tôi cần phần mềm thực sự, không chỉ tài liệu tư vấn.

Hãy:

1. Phản biện thiết kế này và loại bỏ các phần thừa hoặc làm dự án khó triển khai không cần thiết.
2. Đề xuất kiến trúc cuối cùng cho MVP, có thể chạy trên máy cá nhân.
3. Thiết kế database schema hoàn chỉnh và có migration.
4. Thiết kế workflow lưu dữ liệu tăng dần.
5. Thiết kế FTS5 full-text search ngay từ đầu.
6. Thiết kế giao diện quản lý sách và tìm kiếm.
7. Xác định các phần code Javis v0.1.2 có thể tái sử dụng.
8. Bắt đầu lập trình theo từng milestone có kết quả chạy được.
9. Kiểm thử thực tế sau mỗi milestone.
10. Đóng gói source code, README, cấu hình mẫu, lệnh cài đặt và test.
11. Không sửa hoặc xóa dữ liệu đã chưng cất trước đây.
12. Không đưa ra tuyên bố thành công nếu chưa chạy thử chức năng tương ứng.

Nếu thiếu source plugin cũ hoặc checkpoint, hãy yêu cầu tệp cần thiết thay vì tưởng tượng cách chúng hoạt động.

Không tự động mở Batch 13 của quy trình cũ.

---

# XX. ĐỊNH NGHĨA THÀNH CÔNG CUỐI CÙNG

Tôi muốn đạt được trải nghiệm sau:

**Bước 1:** Mở Javis Book Intelligence.

**Bước 2:** Kéo thả một cuốn EPUB bất kỳ.

**Bước 3:** Ứng dụng tự đọc metadata và đưa sách vào thư viện.

**Bước 4:** Tôi chỉnh thể loại, tác giả hoặc phiên bản nếu cần.

**Bước 5:** Chọn model AI, ngân sách và nhấn Start.

**Bước 6:** Ứng dụng tự đọc hiểu, chưng cất và lưu từng đơn vị kiến thức vào database.

**Bước 7:** Khi một phần đã hoàn tất, tôi có thể tìm kiếm nội dung đó ngay, dù sách chưa xử lý xong.

**Bước 8:** Sau khi chưng cất nhiều sách, tôi chỉ cần nhập một từ, cụm từ hoặc câu hỏi vào ô tìm kiếm chung để tra cứu toàn bộ thư viện.

**Bước 9:** Khi mở kết quả, tôi có thể xem bản chưng cất, thông tin sách và nguồn dẫn chứng.

**Bước 10:** Dữ liệu có thể tiếp tục được lập chỉ mục, sao lưu và xuất sang Javis Second Brain.

Ứng dụng phải làm được điều này mà không yêu cầu tôi gõ `OK` sau từng phần sách.

## Thứ tự ưu tiên cuối cùng

**1. Đúng dữ liệu, có dẫn chứng, không làm mất kiến thức.**

**2. Lưu liên tục, bảo đảm toàn vẹn và khả năng phục hồi.**

**3. Tìm kiếm tức thì trên toàn thư viện.**

**4. Tự động hóa tối đa quá trình chưng cất.**

**5. Dễ cài đặt, dễ sử dụng và bảo trì.**

**6. Tối ưu tốc độ và chi phí AI.**

Hãy bắt đầu từ việc thiết kế và xây dựng **Milestone 1: Book Library + SQLite Database + Instant Full-Text Search**, sau đó phát triển AI Distillation Engine trên nền tảng dữ liệu đã hoạt động.

Không chỉ lập kế hoạch. Hãy bắt đầu tạo mã nguồn và bộ kiểm thử thực tế.
