CREATE TABLE books (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL CHECK(length(trim(title)) > 0),
  subtitle TEXT NOT NULL DEFAULT '',
  description TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE TABLE editions (
  id TEXT PRIMARY KEY,
  book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  edition_label TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT '',
  original_language TEXT NOT NULL DEFAULT '',
  publisher TEXT NOT NULL DEFAULT '',
  publication_year INTEGER CHECK(publication_year BETWEEN 0 AND 3000),
  isbn TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_editions_book ON editions(book_id);
CREATE TABLE contributors (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(trim(name)) > 0)
);
CREATE TABLE edition_contributors (
  edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  contributor_id TEXT NOT NULL REFERENCES contributors(id),
  role TEXT NOT NULL DEFAULT 'author',
  PRIMARY KEY (edition_id, contributor_id, role)
);
CREATE TABLE tags (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE COLLATE NOCASE CHECK(length(trim(name)) > 0)
);
CREATE TABLE book_tags (
  book_id TEXT NOT NULL REFERENCES books(id) ON DELETE CASCADE,
  tag_id TEXT NOT NULL REFERENCES tags(id),
  PRIMARY KEY (book_id, tag_id)
);
CREATE TABLE source_files (
  id TEXT PRIMARY KEY,
  edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  sha256 TEXT NOT NULL UNIQUE CHECK(length(sha256) = 64),
  original_filename TEXT NOT NULL,
  storage_name TEXT NOT NULL,
  size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
  imported_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_source_files_edition ON source_files(edition_id);
CREATE TABLE content_units (
  rowid INTEGER PRIMARY KEY AUTOINCREMENT,
  id TEXT NOT NULL UNIQUE,
  edition_id TEXT NOT NULL REFERENCES editions(id) ON DELETE CASCADE,
  source_file_id TEXT NOT NULL REFERENCES source_files(id) ON DELETE CASCADE,
  spine_index INTEGER NOT NULL,
  title TEXT NOT NULL DEFAULT '',
  href TEXT NOT NULL DEFAULT '',
  body_text TEXT NOT NULL,
  char_count INTEGER NOT NULL CHECK(char_count >= 0),
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  UNIQUE(source_file_id, spine_index)
);
CREATE INDEX idx_units_edition ON content_units(edition_id);
CREATE INDEX idx_units_file ON content_units(source_file_id, spine_index);
CREATE VIRTUAL TABLE source_fts USING fts5(
  title, body_text, content='content_units', content_rowid='rowid',
  tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER content_units_ai AFTER INSERT ON content_units BEGIN
  INSERT INTO source_fts(rowid, title, body_text)
  VALUES(new.rowid, new.title, new.body_text);
END;
CREATE TRIGGER content_units_ad AFTER DELETE ON content_units BEGIN
  INSERT INTO source_fts(source_fts, rowid, title, body_text)
  VALUES('delete', old.rowid, old.title, old.body_text);
END;
CREATE TRIGGER content_units_au AFTER UPDATE OF title, body_text ON content_units BEGIN
  INSERT INTO source_fts(source_fts, rowid, title, body_text)
  VALUES('delete', old.rowid, old.title, old.body_text);
  INSERT INTO source_fts(rowid, title, body_text)
  VALUES(new.rowid, new.title, new.body_text);
END;
