"""Parameterized FTS5 search across EPUB source and audited distilled knowledge."""
from __future__ import annotations
import re
from .db import connection

TOKENS = re.compile(r"[^\W_]+(?:['’][^\W_]+)?", re.UNICODE)


def make_match(query: str, mode: str) -> str:
    tokens = TOKENS.findall(query or "")[:24]
    if not tokens:
        return ""
    if mode == "phrase":
        return '"' + " ".join(tokens).replace('"', '""') + '"'
    if mode == "prefix":
        return " OR ".join('"' + t.replace('"', '""') + '"' + ("*" if i == len(tokens)-1 else "")
                           for i, t in enumerate(tokens))
    if mode == "keyword":
        return " OR ".join('"' + t.replace('"', '""') + '"' for t in tokens)
    raise ValueError("Invalid search mode")


SOURCE = '''SELECT 'source' kind, u.id unit_id, NULL distilled_id,
    u.title unit_title, u.href source_href, b.id book_id, b.title book_title,
    e.language language, f.original_filename filename,
    snippet(source_fts,1,'⟦','⟧',' … ',24) snippet,
    bm25(source_fts,4.0,1.0) score, 'source' audit_status
    FROM source_fts JOIN content_units u ON u.rowid=source_fts.rowid
    JOIN editions e ON e.id=u.edition_id JOIN books b ON b.id=e.book_id
    JOIN source_files f ON f.id=u.source_file_id WHERE source_fts MATCH ?'''
DISTILLED = '''SELECT 'distilled' kind, u.id unit_id, d.id distilled_id,
    d.title unit_title, u.href source_href, b.id book_id, b.title book_title,
    e.language language, f.original_filename filename,
    snippet(distilled_fts,1,'⟦','⟧',' … ',24) snippet,
    bm25(distilled_fts,4.0,1.0) score, 'code_only' audit_status
    FROM distilled_fts JOIN distilled_units d ON d.rowid=distilled_fts.rowid AND d.status='published'
    JOIN content_units u ON u.id=d.unit_id
    JOIN editions e ON e.id=u.edition_id JOIN books b ON b.id=e.book_id
    JOIN source_files f ON f.id=u.source_file_id WHERE distilled_fts MATCH ?'''


def search(db_file, query: str, mode='keyword', book_id=None, page=1, per_page=20, scope='all'):
    if scope not in ('all', 'source', 'distilled'):
        raise ValueError('Invalid search scope')
    match = make_match(query, mode)
    page = max(1, int(page))
    per_page = max(1, min(50, int(per_page)))
    if not match:
        return {'items': [], 'total': 0, 'page': page, 'per_page': per_page,
                'query': query, 'scope': scope}
    parts = []
    params = []
    for group, sql in (('source', SOURCE), ('distilled', DISTILLED)):
        if scope not in ('all', group):
            continue
        part = sql + (' AND b.id=?' if book_id else '')
        parts.append(part)
        params.append(match)
        if book_id:
            params.append(book_id)
    union = ' UNION ALL '.join(parts)
    with connection(db_file) as db:
        count = db.execute('SELECT COUNT(*) FROM (' + union + ')', params).fetchone()[0]
        rows = db.execute('''SELECT * FROM (''' + union + ''')
            ORDER BY score ASC, book_title COLLATE NOCASE, unit_id LIMIT ? OFFSET ?''',
            [*params, per_page, (page - 1) * per_page]).fetchall()
    items = []
    for row in rows:
        item = dict(row)
        item['detail_url'] = ('/knowledge/' + item['distilled_id']
                              if item['kind'] == 'distilled' else '/units/' + item['unit_id'])
        items.append(item)
    return {'items': items, 'total': count, 'page': page, 'per_page': per_page,
            'query': query, 'scope': scope}
