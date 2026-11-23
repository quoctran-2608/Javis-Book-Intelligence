# Changelog

## v0.2.0 — Milestone 2 (2026-11-23)

- Thêm OpenAI Responses API adapter với Structured Outputs, prompt versioned và contract Pydantic.
- Thêm hàng đợi SQLite durable có leasing, pause/resume/stop, retries giới hạn, budget preflight và token/cost tracking.
- Thêm checkpoint `drafted` JSON sau API, sau đó transaction audit + source evidence + publish FTS nguyên tử.
- Thêm M2 migration `0003_incremental_engine.sql`, bảo toàn schema và dữ liệu M1.
- Thêm global FTS nguồn/chưng cất, trang knowledge, processing dashboard và API polling.
- Tăng kiểm thử kỹ thuật lên 40 test; thêm script smoke API thực chỉ chạy khi người dùng đồng ý.

## v0.1.0 — Milestone 1 (2026-11-23)

- EPUB import, Library, metadata & editions, SHA-256 deduplication.
- SQLite + FTS5 source full-text search, versioned migration, backup and recovery tests.
