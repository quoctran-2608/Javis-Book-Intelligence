"""Safe, parameterized SQLite FTS5 search (keyword, phrase, prefix)."""
from __future__ import annotations
import re
from .db import connection

TOKENS = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


def make_match(query: str, mode: str) -> str:
    tokens = TOKENS.findall(query or "")[:24]
    if not tokens:
        return ""
    if mode == "phrase":
        # Wrap as a quoted literal FTS phrase, never execute raw user FTS syntax.
        return '"' + " ".join(tokens).replace('"', '""') + '"'
    if mode == "prefix":
        return " OR ".join('"' + t.replace('"', '""') + '"' + ("*" if i == len(tokens)-1 else "")
                           for i, t in enumerate(tokens))
    if mode == "keyword":
        return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
    raise ValueError("Invalid search mode")


def search(db_file, query: str, mode="keyword", book_id=None, page=1, per_page=20):
    match = make_match(query, mode)
    page = max(1, int(page))
    per_page = max(1, min(50, int(per_page)))
    if not match:
        return {"items": [], "total": 0, "page": page, "per_page": per_page, "query": query}
    where = "source_fts MATCH ?"
    params: list = [match]
    if book_id:
        where += " AND b.id = ?"
        params.append(book_id)
    join_sql = """FROM source_fts
        JOIN content_units u ON u.rowid = source_fts.rowid
        JOIN editions e ON e.id = u.edition_id
        JOIN books b ON b.id = e.book_id
        JOIN source_files f ON f.id = u.source_file_id"""
    with connection(db_file) as db:
        total = db.execute(f"SELECT COUNT(*) {join_sql} WHERE {where}", params).fetchone()[0]
        rows = db.execute(f"""SELECT u.id AS unit_id, u.title AS unit_title,
            u.href AS source_href, b.id AS book_id, b.title AS book_title,
            e.language AS language, f.original_filename AS filename,
            snippet(source_fts,1,'⟦','⟧',' … ',24) AS snippet,
            bm25(source_fts,4.0,1.0) AS score
            {join_sql} WHERE {where} ORDER BY score ASC, u.rowid ASC LIMIT ? OFFSET ?""",
            [*params, per_page, (page-1)*per_page]).fetchall()
        return {"items": [dict(row) for row in rows], "total": total,
                "page": page, "per_page": per_page, "query": query}
