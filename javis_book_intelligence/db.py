"""SQLite initialization, versioned migrations, transactions and safe backups."""
from __future__ import annotations
from contextlib import contextmanager
from pathlib import Path
import sqlite3

MIGRATIONS = Path(__file__).resolve().parent / "migrations"


def connect(db_file: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_file), timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=FULL")
    return conn


@contextmanager
def connection(db_file: Path):
    db = connect(db_file)
    try:
        yield db
    finally:
        db.close()


@contextmanager
def transaction(db: sqlite3.Connection):
    db.execute("BEGIN IMMEDIATE")
    try:
        yield db
        db.execute("COMMIT")
    except BaseException:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def initialize(db_file: Path):
    db_file.parent.mkdir(parents=True, exist_ok=True)
    with connection(db_file) as db:
        db.execute("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
        applied = {r[0] for r in db.execute("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS.glob("*.sql")):
            if path.stem in applied:
                continue
            # executescript itself commits pending transactions, so include BEGIN in script.
            safe_version = path.stem.replace("'", "''")
            script = "BEGIN IMMEDIATE;\n" + path.read_text(encoding="utf-8")
            script += f"\nINSERT INTO schema_migrations(version) VALUES('{safe_version}');\nCOMMIT;"
            try:
                db.executescript(script)
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise


def backup(db_file: Path, destination: Path):
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.resolve() == db_file.resolve():
        raise ValueError("Backup destination must differ from database")
    with connection(db_file) as src, sqlite3.connect(str(destination)) as dst:
        src.backup(dst)
    return destination


def rebuild_fts(db_file: Path):
    with connection(db_file) as db, transaction(db):
        db.execute("INSERT INTO source_fts(source_fts) VALUES('rebuild')")
        # The future/distilled index must contain published rows only.
        db.execute("DELETE FROM distilled_fts")
        db.execute("INSERT INTO distilled_fts(rowid,title,body_text) SELECT rowid,title,body_text FROM distilled_units WHERE status='published'")
