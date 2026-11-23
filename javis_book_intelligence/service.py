"""Import EPUB and edit catalog records without modifying original EPUBs."""
from __future__ import annotations
from pathlib import Path
import hashlib
import os
import re
import shutil
import sqlite3
import tempfile
from uuid import uuid4
from .db import connection, transaction
from .epub import parse_epub, EpubError

MAX_UPLOAD = 60 * 1024 * 1024


def _id() -> str:
    return uuid4().hex


def _split_names(s: str) -> list[str]:
    return list(dict.fromkeys(x.strip() for x in re.split(r"[,;\n]", s or "") if x.strip()))


def _contributors(db, edition_id: str, authors: list[str]):
    db.execute("DELETE FROM edition_contributors WHERE edition_id=? AND role='author'", (edition_id,))
    for name in dict.fromkeys(authors):
        row = db.execute("SELECT id FROM contributors WHERE name=? COLLATE NOCASE", (name,)).fetchone()
        contributor_id = row[0] if row else _id()
        if row is None:
            db.execute("INSERT INTO contributors(id,name) VALUES(?,?)", (contributor_id, name))
        db.execute("INSERT INTO edition_contributors VALUES(?,?,'author')", (edition_id, contributor_id))


def import_epub_file(db_file: Path, storage_dir: Path, uploaded_file: Path, filename: str,
                     existing_book_id: str | None = None) -> dict:
    """Atomic DB insert and content-addressed file store. Exact SHA is idempotent."""
    if not filename.lower().endswith('.epub'):
        raise EpubError('Only .epub files are supported')
    if not uploaded_file.is_file() or not (0 < uploaded_file.stat().st_size <= MAX_UPLOAD):
        raise EpubError('EPUB file is empty or exceeds the 60 MB upload limit')
    sha = hashlib.sha256()
    with uploaded_file.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            sha.update(chunk)
    digest = sha.hexdigest()
    with connection(db_file) as db:
        existing = db.execute("""SELECT f.id file_id, b.id book_id, e.id edition_id
            FROM source_files f JOIN editions e ON e.id=f.edition_id
            JOIN books b ON b.id=e.book_id WHERE f.sha256=?""", (digest,)).fetchone()
        if existing:
            return {"status": "duplicate", **dict(existing), "units": 0}
    parsed = parse_epub(uploaded_file)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest = storage_dir / (digest + '.epub')
    created_here = False
    if not dest.exists():
        # Copy on same target filesystem, then atomically rename into final location.
        fd, tmp = tempfile.mkstemp(prefix='incoming_', dir=storage_dir)
        try:
            with os.fdopen(fd, 'wb') as out, uploaded_file.open('rb') as source:
                shutil.copyfileobj(source, out)
            os.replace(tmp, dest)
            created_here = True
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    book_id, edition_id, file_id = _id(), _id(), _id()
    try:
        with connection(db_file) as db, transaction(db):
            existing = db.execute("""SELECT f.id file_id, b.id book_id,e.id edition_id
                FROM source_files f JOIN editions e ON e.id=f.edition_id
                JOIN books b ON b.id=e.book_id WHERE f.sha256=?""", (digest,)).fetchone()
            if existing:
                return {"status":"duplicate", **dict(existing), "units":0}
            if existing_book_id:
                if db.execute("SELECT 1 FROM books WHERE id=?", (existing_book_id,)).fetchone() is None:
                    raise ValueError("Selected existing book was not found")
                book_id = existing_book_id
            else:
                db.execute("INSERT INTO books(id,title,subtitle) VALUES(?,?,?)",
                           (book_id, parsed.title, parsed.subtitle))
            db.execute("""INSERT INTO editions(id,book_id,language,publisher,publication_year,isbn)
                VALUES(?,?,?,?,?,?)""", (edition_id, book_id, parsed.language, parsed.publisher,
                                          parsed.publication_year, parsed.isbn))
            _contributors(db, edition_id, parsed.authors)
            db.execute("""INSERT INTO source_files(id,edition_id,sha256,original_filename,storage_name,size_bytes)
                VALUES(?,?,?,?,?,?)""", (file_id, edition_id, digest, Path(filename).name,
                                             dest.name, uploaded_file.stat().st_size))
            for i, chapter in enumerate(parsed.chapters):
                db.execute("""INSERT INTO content_units
                    (id,edition_id,source_file_id,spine_index,title,href,body_text,char_count)
                    VALUES(?,?,?,?,?,?,?,?)""", (_id(), edition_id, file_id, i, chapter.title,
                                                    chapter.href, chapter.text, len(chapter.text)))
        return {"status":"imported", "book_id":book_id, "edition_id":edition_id,
                "file_id":file_id, "units":len(parsed.chapters)}
    except Exception:
        # Roll back newly copied file only if unreferenced (never remove pre-existing files).
        if created_here:
            with connection(db_file) as db:
                referenced = db.execute("SELECT 1 FROM source_files WHERE sha256=?", (digest,)).fetchone()
            if not referenced:
                dest.unlink(missing_ok=True)
        raise


def list_books(db_file: Path):
    with connection(db_file) as db:
        rows = db.execute("""SELECT b.id,b.title,b.subtitle,b.description,b.created_at,
            COUNT(DISTINCT e.id) AS editions,
            COUNT(DISTINCT u.id) AS units,
            GROUP_CONCAT(DISTINCT c.name) AS authors,
            GROUP_CONCAT(DISTINCT e.language) AS languages,
            GROUP_CONCAT(DISTINCT t.name) AS tags
            FROM books b LEFT JOIN editions e ON e.book_id=b.id
            LEFT JOIN content_units u ON u.edition_id=e.id
            LEFT JOIN edition_contributors ec ON ec.edition_id=e.id AND ec.role='author'
            LEFT JOIN contributors c ON c.id=ec.contributor_id
            LEFT JOIN book_tags bt ON bt.book_id=b.id
            LEFT JOIN tags t ON t.id=bt.tag_id
            GROUP BY b.id ORDER BY b.created_at DESC,b.title COLLATE NOCASE""").fetchall()
        return [dict(row) for row in rows]


def get_book(db_file: Path, book_id: str):
    with connection(db_file) as db:
        book = db.execute("SELECT * FROM books WHERE id=?", (book_id,)).fetchone()
        if book is None:
            return None
        editions = db.execute("SELECT * FROM editions WHERE book_id=? ORDER BY created_at", (book_id,)).fetchall()
        results = []
        for edition in editions:
            e = dict(edition)
            e['authors'] = [r[0] for r in db.execute("""SELECT c.name FROM edition_contributors ec
                JOIN contributors c ON c.id=ec.contributor_id WHERE ec.edition_id=? AND ec.role='author'
                ORDER BY c.name""", (e['id'],))]
            e['files'] = [dict(r) for r in db.execute("SELECT * FROM source_files WHERE edition_id=?", (e['id'],))]
            e['units'] = [dict(r) for r in db.execute("""SELECT u.id,u.spine_index,u.title,u.href,u.char_count
                FROM content_units u WHERE u.edition_id=? ORDER BY u.spine_index""", (e['id'],))]
            results.append(e)
        tags = [r[0] for r in db.execute("""SELECT t.name FROM book_tags bt JOIN tags t ON t.id=bt.tag_id
            WHERE bt.book_id=? ORDER BY t.name""", (book_id,))]
        return {**dict(book), 'editions': results, 'tags': tags}


def get_unit(db_file: Path, unit_id: str):
    with connection(db_file) as db:
        row = db.execute("""SELECT u.*, b.id book_id, b.title book_title,
            e.language language, f.original_filename filename
            FROM content_units u JOIN editions e ON u.edition_id=e.id
            JOIN books b ON e.book_id=b.id JOIN source_files f ON u.source_file_id=f.id
            WHERE u.id=?""", (unit_id,)).fetchone()
        return dict(row) if row else None


def update_book_metadata(db_file: Path, book_id: str, *, title: str, subtitle: str,
                         description: str, tags: str, edition_id: str,
                         authors: str, language: str, publisher: str,
                         publication_year: str, isbn: str, edition_label: str):
    if not title.strip():
        raise ValueError('Title is required')
    year = int(publication_year) if publication_year.strip() else None
    if year is not None and not 0 <= year <= 3000:
        raise ValueError('Publication year is invalid')
    with connection(db_file) as db, transaction(db):
        if db.execute("SELECT 1 FROM books WHERE id=?", (book_id,)).fetchone() is None:
            raise ValueError('Book not found')
        if db.execute("SELECT 1 FROM editions WHERE id=? AND book_id=?", (edition_id, book_id)).fetchone() is None:
            raise ValueError('Edition not found for this book')
        db.execute("""UPDATE books SET title=?,subtitle=?,description=?,updated_at=datetime('now')
                     WHERE id=?""", (title.strip(), subtitle.strip(), description.strip(), book_id))
        db.execute("""UPDATE editions SET language=?,publisher=?,publication_year=?,isbn=?,edition_label=?
                      WHERE id=?""", (language.strip(), publisher.strip(), year, isbn.strip(),
                                    edition_label.strip(), edition_id))
        _contributors(db, edition_id, _split_names(authors))
        db.execute('DELETE FROM book_tags WHERE book_id=?', (book_id,))
        for tag in _split_names(tags):
            tag_row = db.execute('SELECT id FROM tags WHERE name=? COLLATE NOCASE', (tag,)).fetchone()
            tid = tag_row[0] if tag_row else _id()
            if not tag_row:
                db.execute('INSERT INTO tags(id,name) VALUES(?,?)', (tid, tag))
            db.execute('INSERT INTO book_tags VALUES(?,?)', (book_id,tid))
