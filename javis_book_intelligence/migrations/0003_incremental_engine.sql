-- Additive M2 migration. Never modifies or deletes M1 source data.
ALTER TABLE processing_runs ADD COLUMN updated_at TEXT NOT NULL DEFAULT '';
ALTER TABLE processing_runs ADD COLUMN finished_at TEXT;
ALTER TABLE processing_runs ADD COLUMN last_error TEXT NOT NULL DEFAULT '';
ALTER TABLE processing_runs ADD COLUMN stop_reason TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN lease_token TEXT;
ALTER TABLE jobs ADD COLUMN lease_until REAL;
ALTER TABLE jobs ADD COLUMN next_retry_at REAL NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN input_sha256 TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN input_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN output_tokens INTEGER NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN cost_usd REAL NOT NULL DEFAULT 0;
ALTER TABLE jobs ADD COLUMN response_id TEXT NOT NULL DEFAULT '';
ALTER TABLE jobs ADD COLUMN finished_at TEXT;
CREATE INDEX idx_jobs_claimable ON jobs(status, next_retry_at, lease_until);
-- Claiming is atomic (BEGIN IMMEDIATE), and lease tokens prevent stale workers
-- from publishing results after ownership has moved to another worker.
-- Durable response checkpoint: a crash after API success but before publication
-- does not require calling the provider again once JSON + usage were committed.
ALTER TABLE jobs ADD COLUMN result_json TEXT;
