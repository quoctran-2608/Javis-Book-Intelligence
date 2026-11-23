-- Reserved storage schema for Milestone 2/3. NOT an implemented AI pipeline.
CREATE TABLE processing_runs (
 id TEXT PRIMARY KEY,
 source_file_id TEXT NOT NULL REFERENCES source_files(id),
 mode TEXT NOT NULL,
 model TEXT NOT NULL,
 prompt_version TEXT NOT NULL,
 config_json TEXT NOT NULL DEFAULT '{}',
 state TEXT NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','processing','paused','completed','failed')),
 budget_usd REAL CHECK(budget_usd IS NULL OR budget_usd >= 0),
 spent_usd REAL NOT NULL DEFAULT 0 CHECK(spent_usd >= 0),
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE jobs (
 id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES processing_runs(id),
 unit_id TEXT NOT NULL REFERENCES content_units(id),
 status TEXT NOT NULL CHECK(status IN ('pending','processing','drafted','auditing','completed','needs_review','retry_waiting','failed')),
 attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts >= 0),
 error TEXT NOT NULL DEFAULT '',
 updated_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(run_id, unit_id)
);
CREATE INDEX idx_jobs_run_status ON jobs(run_id,status);
CREATE TABLE distilled_units (
 id TEXT PRIMARY KEY,
 run_id TEXT NOT NULL REFERENCES processing_runs(id),
 unit_id TEXT NOT NULL REFERENCES content_units(id),
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','needs_review','published')),
 title TEXT NOT NULL DEFAULT '',
 body_text TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now')),
 updated_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(run_id,unit_id)
);
CREATE TABLE distilled_revisions (
 id TEXT PRIMARY KEY,
 distilled_id TEXT NOT NULL REFERENCES distilled_units(id) ON DELETE CASCADE,
 revision_no INTEGER NOT NULL CHECK(revision_no >= 1),
 body_text TEXT NOT NULL,
 model TEXT NOT NULL DEFAULT '',
 prompt_version TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now')),
 UNIQUE(distilled_id,revision_no)
);
CREATE TABLE claims (
 id TEXT PRIMARY KEY,
 distilled_id TEXT NOT NULL REFERENCES distilled_units(id) ON DELETE CASCADE,
 text TEXT NOT NULL,
 ordinal INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE evidence (
 id TEXT PRIMARY KEY,
 claim_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
 unit_id TEXT NOT NULL REFERENCES content_units(id),
 quote TEXT NOT NULL,
 source_href TEXT NOT NULL DEFAULT ''
);
CREATE TABLE audit_results (
 id TEXT PRIMARY KEY,
 distilled_id TEXT NOT NULL REFERENCES distilled_units(id) ON DELETE CASCADE,
 audit_kind TEXT NOT NULL CHECK(audit_kind IN ('code','semantic','human')),
 passed INTEGER NOT NULL CHECK(passed IN (0,1)),
 details_json TEXT NOT NULL DEFAULT '{}',
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE knowledge_links (
 from_id TEXT NOT NULL REFERENCES distilled_units(id) ON DELETE CASCADE,
 to_id TEXT NOT NULL REFERENCES distilled_units(id) ON DELETE CASCADE,
 relation TEXT NOT NULL,
 PRIMARY KEY(from_id,to_id,relation)
);
CREATE TABLE sync_jobs (
 id TEXT PRIMARY KEY,
 resource TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending',
 attempts INTEGER NOT NULL DEFAULT 0,
 error TEXT NOT NULL DEFAULT '',
 created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE VIRTUAL TABLE distilled_fts USING fts5(
 title, body_text, tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER distilled_ai AFTER INSERT ON distilled_units WHEN new.status='published' BEGIN
  INSERT INTO distilled_fts(rowid,title,body_text) VALUES(new.rowid,new.title,new.body_text);
END;
CREATE TRIGGER distilled_ad AFTER DELETE ON distilled_units WHEN old.status='published' BEGIN
  DELETE FROM distilled_fts WHERE rowid=old.rowid;
END;
CREATE TRIGGER distilled_au AFTER UPDATE OF title,body_text,status ON distilled_units BEGIN
  DELETE FROM distilled_fts WHERE rowid=old.rowid AND old.status='published';
  INSERT INTO distilled_fts(rowid,title,body_text)
    SELECT new.rowid,new.title,new.body_text WHERE new.status='published';
END;
