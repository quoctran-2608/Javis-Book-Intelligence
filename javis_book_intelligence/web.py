"""Single-user localhost FastAPI application and durable M2 processing dashboard."""
from __future__ import annotations
from contextlib import asynccontextmanager
import os
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import quote, urlsplit
from fastapi import FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, RedirectResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.templating import Jinja2Templates
from .db import initialize, connection
from .epub import EpubError
from .engine import Worker, create_run, list_runs, get_run, get_knowledge, control_run, raise_budget, retry_review
from .providers import OpenAIResponsesProvider
from .search import search
from .service import MAX_UPLOAD, import_epub_file, get_book, get_unit, list_books, update_book_metadata

BASE = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE / 'templates'))


def create_app(data_dir: Path | str | None = None, *, provider=None, start_worker: bool = True) -> FastAPI:
    folder = Path(data_dir or os.environ.get('JAVIS_DATA_DIR', '~/.javis_book_intelligence')).expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    db_file = folder / 'library.db'
    storage = folder / 'epubs'
    storage.mkdir(parents=True, exist_ok=True)
    initialize(db_file)
    worker = Worker(db_file, provider=provider)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        if start_worker:
            worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(title='Javis Book Intelligence', version='0.2.0', lifespan=lifespan,
                  description='M1 library/search + M2 OpenAI distillation and incremental FTS')
    # Protect localhost-only service against DNS-rebinding and Host spoofing.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1', 'localhost', 'testserver'])
    app.state.db_file = db_file
    app.state.storage = storage
    app.state.worker = worker
    app.mount('/static', StaticFiles(directory=str(BASE / 'static')), name='static')

    @app.middleware('http')
    async def same_origin_writes(request: Request, call_next):
        # A remote webpage can POST to localhost even with CORS disabled.
        # Browser Origin is checked for all state-changing actions; curl and
        # native clients without Origin are local trusted clients only.
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            origin = request.headers.get('origin')
            if origin:
                parsed = urlsplit(origin)
                if parsed.netloc.lower() != request.headers.get('host', '').lower() or parsed.scheme not in ('http', 'https'):
                    return PlainTextResponse('Cross-origin writes not allowed', status_code=403)
        return await call_next(request)

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
            source_units = db.execute('SELECT COUNT(*) FROM content_units').fetchone()[0]
            distilled = db.execute('SELECT COUNT(*) FROM distilled_units WHERE status="published"').fetchone()[0]
        return {'status': 'ok', 'milestone': 2, 'schema_version': version,
                'source_units': source_units, 'published_distilled_units': distilled}

    @app.get('/api/books')
    def api_books():
        return {'books': list_books(db_file)}

    @app.post('/books/import')
    async def upload_epubs(files: list[UploadFile] = File(...), existing_book_id: str = Form(default='')):
        successes, duplicates, problems = [], [], []
        for upload in files:
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
        return TEMPLATES.TemplateResponse(request, 'book.html', {'book': b, 'notice': notice,
                                                                 'has_api_key': bool(os.getenv('OPENAI_API_KEY'))})

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
                   per_page: int = Query(20, ge=1, le=50), scope: str = 'all'):
        if mode not in ('keyword', 'phrase', 'prefix') or scope not in ('all', 'source', 'distilled'):
            raise HTTPException(422, detail='Invalid search mode or scope')
        return search(db_file, q, mode, book_id, page, per_page, scope)

    @app.get('/knowledge/{distilled_id}', response_class=HTMLResponse)
    def knowledge_detail(distilled_id: str, request: Request):
        item = get_knowledge(db_file, distilled_id)
        if not item:
            raise HTTPException(404, detail='Knowledge unit not found')
        return TEMPLATES.TemplateResponse(request, 'knowledge.html', {'item': item})

    @app.get('/processing', response_class=HTMLResponse)
    def processing_home(request: Request, notice: str = ''):
        return TEMPLATES.TemplateResponse(request, 'processing.html',
                                          {'runs': list_runs(db_file), 'notice': notice})

    @app.get('/api/processing/runs')
    def processing_runs():
        return {'runs': list_runs(db_file)}

    @app.post('/processing/create')
    def create_processing(source_file_id: str = Form(...), mode: str = Form('general'),
                          model: str = Form(...), language: str = Form('vi'),
                          budget_usd: float = Form(...), input_price: float = Form(...),
                          output_price: float = Form(...), unit_limit: int = Form(20),
                          max_source_chars: int = Form(12000), max_output_tokens: int = Form(1800),
                          max_attempts: int = Form(3)):
        # If the app uses its real provider, refuse jobs that cannot run.
        if isinstance(worker.provider, OpenAIResponsesProvider) and not os.getenv('OPENAI_API_KEY'):
            msg = 'Chưa cấu hình OPENAI_API_KEY trên máy. Không khởi chạy AI.'
            return RedirectResponse('/processing?notice=' + quote(msg), status_code=303)
        try:
            run_id = create_run(db_file, source_file_id=source_file_id, mode=mode,
                model=model, language=language, budget_usd=budget_usd,
                input_price=input_price, output_price=output_price, unit_limit=unit_limit,
                max_source_chars=max_source_chars, max_output_tokens=max_output_tokens,
                max_attempts=max_attempts)
        except ValueError as exc:
            return RedirectResponse('/processing?notice=' + quote(str(exc)), status_code=303)
        return RedirectResponse('/processing/' + run_id, status_code=303)

    @app.get('/processing/{run_id}', response_class=HTMLResponse)
    def processing_run_detail(run_id: str, request: Request, notice: str = ''):
        run = get_run(db_file, run_id)
        if not run:
            raise HTTPException(404, detail='Run not found')
        return TEMPLATES.TemplateResponse(request, 'processing_run.html', {'run': run, 'notice': notice})

    @app.get('/api/processing/runs/{run_id}')
    def processing_run_api(run_id: str):
        run = get_run(db_file, run_id)
        if not run:
            raise HTTPException(404, detail='Run not found')
        return run

    @app.post('/processing/{run_id}/action')
    def processing_action(run_id: str, action: str = Form(...)):
        try:
            control_run(db_file, run_id, action)
            msg = 'Đã áp dụng: ' + action
        except ValueError as exc:
            msg = 'Không thể thực hiện: ' + str(exc)
        return RedirectResponse('/processing/' + run_id + '?notice=' + quote(msg), status_code=303)

    @app.post('/processing/{run_id}/budget')
    def processing_budget(run_id: str, budget_usd: float = Form(...)):
        try:
            raise_budget(db_file, run_id, budget_usd)
            msg = 'Đã nâng giới hạn ngân sách. Nhấn Resume để tiếp tục.'
        except ValueError as exc:
            msg = 'Không thể sửa ngân sách: ' + str(exc)
        return RedirectResponse('/processing/' + run_id + '?notice=' + quote(msg), status_code=303)

    @app.post('/processing/{run_id}/retry/{job_id}')
    def processing_retry(run_id: str, job_id: str):
        run = get_run(db_file, run_id)
        if not run or job_id not in {job['id'] for job in run['jobs']}:
            raise HTTPException(404, detail='Job not found in this run')
        try:
            retry_review(db_file, job_id)
            msg = 'Đã đưa tác vụ về pending. Nhấn Resume để tiếp tục.'
        except ValueError as exc:
            msg = 'Không thể retry: ' + str(exc)
        return RedirectResponse('/processing/' + run_id + '?notice=' + quote(msg), status_code=303)

    return app
