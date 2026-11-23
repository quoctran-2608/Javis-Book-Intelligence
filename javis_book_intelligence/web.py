"""Local-only single-user FastAPI UI and JSON search API."""
from __future__ import annotations
import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import quote
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .db import initialize, connection
from .epub import EpubError
from .search import search
from .service import MAX_UPLOAD, import_epub_file, get_book, get_unit, list_books, update_book_metadata

BASE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE / 'templates'))


def create_app(data_dir: Path | str | None = None) -> FastAPI:
    folder = Path(data_dir or os.environ.get('JAVIS_DATA_DIR', '~/.javis_book_intelligence')).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    db_file = folder / 'library.db'
    storage = folder / 'epubs'
    storage.mkdir(parents=True, exist_ok=True)
    initialize(db_file)
    app = FastAPI(title='Javis Book Intelligence', version='0.1.0',
                  description='Milestone 1: EPUB Library + SQLite + FTS5')
    app.state.db_file = db_file
    app.state.storage = storage
    app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')

    @app.get('/', response_class=HTMLResponse)
    def index(request: Request, notice: str = ''):
        books = list_books(db_file)
        return TEMPLATES.TemplateResponse(request, 'index.html',
                        {'books': books, 'notice': notice, 'book_count': len(books),
                         'unit_count': sum(int(b['units']) for b in books)})

    @app.get('/api/health')
    def health():
        with connection(db_file) as db:
            version = db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0]
            fts = db.execute("SELECT COUNT(*) FROM content_units").fetchone()[0]
        return {'status': 'ok', 'milestone': 1, 'schema_version': version, 'source_units': fts}

    @app.get('/api/books')
    def api_books():
        return {'books': list_books(db_file)}

    @app.post('/books/import')
    async def upload_epubs(files: list[UploadFile] = File(...), existing_book_id: str = Form(default='')):
        successes, duplicates, problems = [], [], []
        for upload in files:
            # SpooledUploadFile is not trusted as an actual EPUB until parsed.
            fd, name = tempfile.mkstemp(prefix='epub_', suffix='.epub', dir=folder)
            staged = Path(name)
            try:
                size = 0
                with os.fdopen(fd, 'wb') as out:
                    while chunk := await upload.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_UPLOAD:
                            raise EpubError('Exceeded 60 MB upload limit')
                        out.write(chunk)
                result = import_epub_file(db_file, storage, staged, upload.filename or 'unknown.epub',
                                          existing_book_id or None)
                (duplicates if result['status'] == 'duplicate' else successes).append(result)
            except (EpubError, ValueError, OSError) as e:
                problems.append(f'{upload.filename}: {e}')
            finally:
                staged.unlink(missing_ok=True)
                await upload.close()
        notice = f'Đã nhập {len(successes)} EPUB; trùng SHA-256: {len(duplicates)}.'
        if problems:
            notice += ' Lỗi: ' + ' | '.join(problems)[:800]
        return RedirectResponse('/?notice=' + quote(notice), status_code=303)

    @app.get('/books/{book_id}', response_class=HTMLResponse)
    def book_detail(book_id: str, request: Request, notice: str = ''):
        b = get_book(db_file, book_id)
        if not b:
            raise HTTPException(status_code=404, detail='Book not found')
        return TEMPLATES.TemplateResponse(request, 'book.html', {'book': b, 'notice': notice})

    @app.post('/books/{book_id}/metadata')
    def save_metadata(book_id: str, title: str = Form(...), edition_id: str = Form(...),
                      subtitle: str = Form(''), description: str = Form(''),
                      tags: str = Form(''), authors: str = Form(''),
                      language: str = Form(''), publisher: str = Form(''),
                      publication_year: str = Form(''), isbn: str = Form(''),
                      edition_label: str = Form('')):
        try:
            update_book_metadata(db_file, book_id, title=title, subtitle=subtitle,
                description=description, tags=tags, edition_id=edition_id,
                authors=authors, language=language, publisher=publisher,
                publication_year=publication_year, isbn=isbn, edition_label=edition_label)
            msg = 'Đã lưu metadata.'
        except (ValueError, sqlite3.IntegrityError) as e:
            msg = 'Không thể lưu: ' + str(e)
        return RedirectResponse(f'/books/{book_id}?notice=' + quote(msg), status_code=303)

    @app.get('/units/{unit_id}', response_class=HTMLResponse)
    def unit_detail(unit_id: str, request: Request):
        u = get_unit(db_file, unit_id)
        if not u:
            raise HTTPException(status_code=404, detail='Unit not found')
        return TEMPLATES.TemplateResponse(request, 'unit.html', {'unit': u})

    @app.get('/files/{file_id}')
    def download_epub(file_id: str):
        with connection(db_file) as db:
            file = db.execute('SELECT original_filename,storage_name FROM source_files WHERE id=?', (file_id,)).fetchone()
        if not file:
            raise HTTPException(404, 'Source EPUB file not found')
        path = storage / file['storage_name']
        if path.parent != storage or not path.is_file():
            raise HTTPException(404, 'Stored EPUB is unavailable')
        return FileResponse(path, filename=file['original_filename'], media_type='application/epub+zip')

    @app.get('/search', response_class=HTMLResponse)
    def search_page(request: Request):
        return TEMPLATES.TemplateResponse(request, 'search.html', {})

    @app.get('/api/search')
    def api_search(q: str = Query(default='', max_length=1000), mode: str = 'keyword',
                   book_id: str | None = None, page: int = Query(1, ge=1),
                   per_page: int = Query(20, ge=1, le=50)):
        if mode not in ('keyword','phrase','prefix'):
            raise HTTPException(422, detail='mode must be keyword, phrase or prefix')
        return search(db_file, q, mode, book_id, page, per_page)

    return app


