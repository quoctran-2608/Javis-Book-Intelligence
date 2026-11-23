"""M2 durable single-unit AI queue: SQLite leases, checkpointed publishes, retries.

External API calls are at-least-once after a crash; DB publication is idempotent.
Only the database transaction changes a unit from draft to FTS-visible.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
import sqlite3
import threading
import time
from pathlib import Path
from uuid import uuid4
from .db import connection, transaction
from .distillation import audit_output, render_body, PROMPT_VERSION, instructions, user_input
from .providers import AIResponse, OpenAIResponsesProvider, ProviderError

LEASE_SECONDS = 300.0
MAX_INPUT_CHARS = 100_000


def new_id() -> str:
    return uuid4().hex


def _configs(*, language: str, input_price: float, output_price: float,
             max_source_chars: int, max_output_tokens: int, max_attempts: int) -> dict:
    if not language or len(language) > 35 or any(x in language for x in '<>{}\n\r'):
        raise ValueError('Output language is invalid')
    for price in (input_price, output_price):
        if not math.isfinite(price) or not 0 < price <= 10000:
            raise ValueError('Explicit, positive USD-per-million token rates are required')
    if not 100 <= max_source_chars <= MAX_INPUT_CHARS:
        raise ValueError('max_source_chars must be between 100 and 100000')
    if not 256 <= max_output_tokens <= 16000:
        raise ValueError('max_output_tokens must be between 256 and 16000')
    if not 1 <= max_attempts <= 6:
        raise ValueError('max_attempts must be between 1 and 6')
    return {'language': language.strip(), 'input_price': float(input_price),
            'output_price': float(output_price), 'max_source_chars': max_source_chars,
            'max_output_tokens': max_output_tokens, 'max_attempts': max_attempts,
            'audit_policy': 'code_only', 'provider': 'openai'}


def create_run(db_file: Path, *, source_file_id: str, mode: str, model: str,
               language: str = 'vi', budget_usd: float = 1.0, input_price: float = 1.0,
               output_price: float = 4.0, max_source_chars: int = 12000,
               max_output_tokens: int = 1800, max_attempts: int = 3,
               unit_limit: int = 20) -> str:
    """One explicit user approval authorizes at most `unit_limit` source units.

    The rates are user-provided price assumptions, not fetched provider prices.
    Each job refers to a complete M1 XHTML unit; oversized units are quarantined.
    """
    if mode not in ('general', 'dictionary'):
        raise ValueError('Unsupported distillation mode')
    if not model.strip() or len(model) > 100 or any(c.isspace() for c in model):
        raise ValueError('Model ID is invalid')
    if not math.isfinite(budget_usd) or not 0 < budget_usd <= 100000:
        raise ValueError('Budget must be a positive USD amount')
    if not 1 <= unit_limit <= 5000:
        raise ValueError('unit_limit must be between 1 and 5000')
    config = _configs(language=language, input_price=input_price, output_price=output_price,
                      max_source_chars=max_source_chars, max_output_tokens=max_output_tokens,
                      max_attempts=max_attempts)
    run_id = new_id()
    with connection(db_file) as db, transaction(db):
        if db.execute('SELECT 1 FROM source_files WHERE id=?', (source_file_id,)).fetchone() is None:
            raise ValueError('EPUB source file not found')
        units = db.execute('SELECT id FROM content_units WHERE source_file_id=? ORDER BY spine_index LIMIT ?',
                           (source_file_id, unit_limit)).fetchall()
        if not units:
            raise ValueError('No EPUB source units found')
        db.execute('''INSERT INTO processing_runs
            (id,source_file_id,mode,model,prompt_version,config_json,state,budget_usd,updated_at)
            VALUES(?,?,?,?,?,?,"processing",?,datetime('now'))''',
                   (run_id, source_file_id, mode, model.strip(), PROMPT_VERSION,
                    json.dumps(config, ensure_ascii=False), budget_usd))
        db.executemany('''INSERT INTO jobs(id,run_id,unit_id,status) VALUES(?,?,?,"pending")''',
                       [(new_id(), run_id, u['id']) for u in units])
    return run_id


def list_runs(db_file: Path) -> list[dict]:
    with connection(db_file) as db:
        rows = db.execute('''SELECT r.id, r.state, r.stop_reason, r.last_error, r.mode, r.model,
            r.budget_usd, r.spent_usd, r.created_at, r.finished_at,
            b.title AS book_title, b.id AS book_id,
            COUNT(j.id) AS total_jobs,
            SUM(CASE WHEN j.status='completed' THEN 1 ELSE 0 END) AS completed_jobs,
            SUM(CASE WHEN j.status='needs_review' THEN 1 ELSE 0 END) AS needs_review_jobs,
            SUM(CASE WHEN j.status='failed' THEN 1 ELSE 0 END) AS failed_jobs
            FROM processing_runs r JOIN source_files f ON f.id=r.source_file_id
            JOIN editions e ON e.id=f.edition_id JOIN books b ON b.id=e.book_id
            LEFT JOIN jobs j ON j.run_id=r.id
            GROUP BY r.id ORDER BY r.created_at DESC, r.rowid DESC''').fetchall()
    return [dict(row) for row in rows]


def get_run(db_file: Path, run_id: str) -> dict | None:
    with connection(db_file) as db:
        run = db.execute('''SELECT r.*, b.title AS book_title, b.id AS book_id,
            f.original_filename AS source_filename FROM processing_runs r
            JOIN source_files f ON f.id=r.source_file_id
            JOIN editions e ON e.id=f.edition_id JOIN books b ON b.id=e.book_id
            WHERE r.id=?''', (run_id,)).fetchone()
        if run is None:
            return None
        result = dict(run)
        result['config'] = json.loads(result.pop('config_json'))
        result['jobs'] = [dict(x) for x in db.execute('''SELECT j.id, j.unit_id, j.status, j.attempts,
            j.error, j.input_tokens, j.output_tokens, j.cost_usd, j.response_id,
            u.title AS unit_title, u.href, d.id AS distilled_id
            FROM jobs j JOIN content_units u ON u.id=j.unit_id
            LEFT JOIN distilled_units d ON d.run_id=j.run_id AND d.unit_id=j.unit_id
            WHERE j.run_id=? ORDER BY u.spine_index''', (run_id,)).fetchall()]
        result['summary'] = {status: sum(j['status'] == status for j in result['jobs'])
                             for status in ('pending', 'processing', 'drafted', 'retry_waiting', 'completed',
                                            'needs_review', 'failed')}
        return result


def control_run(db_file: Path, run_id: str, action: str) -> None:
    if action not in ('pause', 'resume', 'stop'):
        raise ValueError('Unknown run action')
    with connection(db_file) as db, transaction(db):
        run = db.execute('SELECT state, stop_reason FROM processing_runs WHERE id=?', (run_id,)).fetchone()
        if not run:
            raise ValueError('Run not found')
        state = run['state']
        if action == 'pause':
            if state != 'processing':
                raise ValueError('Only processing runs can be paused')
            db.execute('UPDATE processing_runs SET state="paused", last_error="", updated_at=datetime("now") WHERE id=?', (run_id,))
        elif action == 'stop':
            if state not in ('paused', 'processing'):
                raise ValueError('Run is not active')
            # The original schema constrains states; stop_reason distinguishes
            # intentional stopping from errors, without rebuilding old tables.
            db.execute('''UPDATE processing_runs SET state='failed', stop_reason='user_stopped',
                last_error='Stopped by user; committed knowledge remains available',
                updated_at=datetime('now'), finished_at=datetime('now') WHERE id=?''', (run_id,))
        else:
            if state != 'paused':
                if state != 'failed':
                    raise ValueError('Only paused or recoverable failed runs can resume')
                pending = db.execute('SELECT COUNT(*) FROM jobs WHERE run_id=? AND status="pending"', (run_id,)).fetchone()[0]
                if not pending and run['stop_reason'] != 'user_stopped':
                    raise ValueError('Re-queue a failed job before resuming')
            db.execute('''UPDATE processing_runs SET state='processing', stop_reason='',
                last_error='', finished_at=NULL, updated_at=datetime('now') WHERE id=?''', (run_id,))


def raise_budget(db_file: Path, run_id: str, new_budget_usd: float):
    if not math.isfinite(new_budget_usd) or new_budget_usd <= 0 or new_budget_usd > 100000:
        raise ValueError('Budget must be positive and finite')
    with connection(db_file) as db, transaction(db):
        run = db.execute('SELECT budget_usd, spent_usd FROM processing_runs WHERE id=?', (run_id,)).fetchone()
        if not run:
            raise ValueError('Run not found')
        if new_budget_usd <= run['budget_usd'] or new_budget_usd < run['spent_usd']:
            raise ValueError('New budget must be higher than the previous budget and spent amount')
        db.execute('UPDATE processing_runs SET budget_usd=?, updated_at=datetime("now") WHERE id=?',
                   (new_budget_usd, run_id))


def retry_review(db_file: Path, job_id: str):
    with connection(db_file) as db, transaction(db):
        row = db.execute('''SELECT j.status, j.run_id, r.state FROM jobs j
            JOIN processing_runs r ON r.id=j.run_id WHERE j.id=?''', (job_id,)).fetchone()
        if row is None or row['status'] not in ('needs_review', 'failed'):
            raise ValueError('Only failed or needs_review jobs can retry')
        if row['state'] == 'processing':
            raise ValueError('Pause the run before manually re-queuing jobs')
        db.execute('''UPDATE jobs SET status='pending', attempts=0, error='', next_retry_at=0,
            lease_token=NULL, lease_until=NULL, finished_at=NULL, updated_at=datetime('now') WHERE id=?''', (job_id,))
        # Important: old draft + audit history are retained for traceability.
        if row['state'] == 'completed':
            db.execute('UPDATE processing_runs SET state="paused", finished_at=NULL WHERE id=?', (row['run_id'],))


def _maybe_finalize(db: sqlite3.Connection, run_id: str) -> None:
    open_count = db.execute('''SELECT COUNT(*) FROM jobs WHERE run_id=? AND
        status IN ('pending','processing','drafted','auditing','retry_waiting')''', (run_id,)).fetchone()[0]
    if open_count:
        return
    row = db.execute('SELECT state,stop_reason FROM processing_runs WHERE id=?', (run_id,)).fetchone()
    if row is None or row['stop_reason']:
        return
    failed = db.execute('SELECT COUNT(*) FROM jobs WHERE run_id=? AND status="failed"', (run_id,)).fetchone()[0]
    state = 'failed' if failed else 'completed'
    error = 'Some jobs failed; inspect and retry as needed' if failed else ''
    db.execute('''UPDATE processing_runs SET state=?, last_error=?, finished_at=datetime('now'),
        updated_at=datetime('now') WHERE id=?''', (state, error, run_id))


@dataclass(frozen=True)
class ClaimedJob:
    job_id: str
    run_id: str
    unit_id: str
    token: str
    attempts: int
    source_hash: str
    model: str
    mode: str
    config: dict
    title: str
    href: str
    body: str
    estimated_usd: float
    drafted: bool = False


class Worker:
    """One worker per Python process; claims are SQLite-atomic across processes."""
    def __init__(self, db_file: Path, provider=None, poll_seconds: float = 1.0):
        self.db_file = db_file
        self.provider = provider if provider is not None else OpenAIResponsesProvider()
        self.poll_seconds = poll_seconds
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name='javis-distillation-worker', daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        # A request that is already with the provider may still finish and commit.
        if self._thread:
            self._thread.join(timeout=0.5)

    def _run(self):
        while not self._stop.is_set():
            try:
                worked = self.run_once()
            except Exception:
                # Never log raw exceptions: some provider exceptions may contain
                # a key, the source text, or the provider response body.
                # A failed database publish leaves the response in 'drafted'.
                worked = False
            if not worked:
                self._stop.wait(self.poll_seconds)

    def claim(self, now: float | None = None) -> ClaimedJob | None:
        now = time.time() if now is None else now
        with connection(self.db_file) as db, transaction(db):
            row = db.execute('''SELECT j.id job_id, j.run_id, j.unit_id, j.attempts,
                j.status, j.input_sha256, r.model, r.mode, r.config_json,
                r.budget_usd, r.spent_usd, u.title, u.href, u.body_text
                FROM jobs j JOIN processing_runs r ON r.id=j.run_id
                JOIN content_units u ON u.id=j.unit_id
                WHERE r.state='processing' AND NOT EXISTS (
                    SELECT 1 FROM jobs active WHERE active.run_id=j.run_id AND active.id!=j.id
                    AND active.status='processing' AND active.lease_until>?
                ) AND (
                    j.status='pending' OR
                    (j.status='retry_waiting' AND j.next_retry_at<=?) OR
                    (j.status='processing' AND j.lease_until IS NOT NULL AND j.lease_until<=?) OR
                    (j.status='drafted' AND j.next_retry_at<=? AND
                        (j.lease_until IS NULL OR j.lease_until<=?))
                ) ORDER BY r.created_at, r.rowid, u.spine_index LIMIT 1''',
                (now, now, now, now, now)).fetchone()
            if row is None:
                return None
            config = json.loads(row['config_json'])
            token = new_id()
            digest = sha256(row['body_text'].encode('utf-8')).hexdigest()
            if row['status'] == 'drafted':
                # Audit an already persisted response, without another API call
                # or incrementing the number of provider attempts.
                db.execute('''UPDATE jobs SET lease_token=?,lease_until=?,error='',
                    updated_at=datetime('now') WHERE id=?''',
                    (token, now + LEASE_SECONDS, row['job_id']))
                return ClaimedJob(job_id=row['job_id'], run_id=row['run_id'],
                                  unit_id=row['unit_id'], token=token, attempts=row['attempts'],
                                  source_hash=row['input_sha256'], model=row['model'],
                                  mode=row['mode'], config=config, title=row['title'],
                                  href=row['href'], body=row['body_text'],
                                  estimated_usd=0, drafted=True)
            if row['attempts'] >= config['max_attempts']:
                db.execute('''UPDATE jobs SET status='failed',error='Maximum attempts reached after recovery',
                    lease_token=NULL,lease_until=NULL,finished_at=datetime('now') WHERE id=?''',
                    (row['job_id'],))
                _maybe_finalize(db, row['run_id'])
                return None
            prompt_bytes = len((instructions(row['mode'], config['language']) +
                                user_input(row['title'], row['href'], row['body_text'])).encode('utf-8'))
            projected = (prompt_bytes * config['input_price'] +
                         config['max_output_tokens'] * config['output_price']) / 1_000_000
            if len(row['body_text']) <= config['max_source_chars'] and row['spent_usd'] + projected > row['budget_usd'] + 1e-9:
                db.execute('''UPDATE processing_runs SET state='paused',
                    last_error='Budget preflight limit reached; raise budget and resume',
                    updated_at=datetime('now') WHERE id=?''', (row['run_id'],))
                return None
            db.execute('''UPDATE jobs SET status='processing', attempts=attempts+1,
                lease_token=?, lease_until=?, input_sha256=?, result_json=NULL,
                next_retry_at=0, updated_at=datetime('now'), error='' WHERE id=?''',
                (token, now + LEASE_SECONDS, digest, row['job_id']))
            return ClaimedJob(job_id=row['job_id'], run_id=row['run_id'], unit_id=row['unit_id'],
                              token=token, attempts=row['attempts'] + 1, source_hash=digest,
                              model=row['model'], mode=row['mode'], config=config,
                              title=row['title'], href=row['href'], body=row['body_text'],
                              estimated_usd=projected)

    @staticmethod
    def _owns(db: sqlite3.Connection, job: ClaimedJob, status: str) -> bool:
        row = db.execute('SELECT status,lease_token FROM jobs WHERE id=?', (job.job_id,)).fetchone()
        return bool(row and row['status'] == status and row['lease_token'] == job.token)

    def _record_provider_error(self, job: ClaimedJob, issues: list[str], *, retryable: bool, pause_on_error: bool = False):
        with connection(self.db_file) as db, transaction(db):
            if not self._owns(db, job, 'processing'):
                return
            if retryable and job.attempts < job.config['max_attempts']:
                wait = min(120, 2 ** max(0, job.attempts - 1))
                status, next_retry = 'retry_waiting', time.time() + wait
            else:
                status, next_retry = 'failed', 0
            db.execute('''UPDATE jobs SET status=?,error=?,next_retry_at=?, lease_token=NULL,
                lease_until=NULL,finished_at=?,updated_at=datetime('now') WHERE id=?''',
                (status, '; '.join(issues)[:500], next_retry,
                 None if status == 'retry_waiting' else time.strftime('%Y-%m-%d %H:%M:%S'), job.job_id))
            if pause_on_error:
                open_job = db.execute("SELECT 1 FROM jobs WHERE run_id=? AND status IN ('pending','retry_waiting','processing','drafted') LIMIT 1",
                                      (job.run_id,)).fetchone()
                if open_job:
                    db.execute("""UPDATE processing_runs SET state='paused',last_error=?,updated_at=datetime('now')
                        WHERE id=? AND state='processing'""",
                        ('Non-retryable provider error; inspect configuration and resume', job.run_id))
                else:
                    _maybe_finalize(db, job.run_id)
            else:
                _maybe_finalize(db, job.run_id)

    def _persist_response(self, job: ClaimedJob, response: AIResponse) -> bool:
        """Durably checkpoint model JSON, token usage and cost before auditing."""
        raw_json = json.dumps(response.payload, ensure_ascii=False)
        if len(raw_json) > 500_000:
            # This is a hard safety cap against malformed/bloated responses.
            self._record_provider_error(job, ['Provider JSON exceeded 500 KB cap'], retryable=False)
            return False
        cost = (response.input_tokens * job.config['input_price'] +
                response.output_tokens * job.config['output_price']) / 1_000_000
        with connection(self.db_file) as db, transaction(db):
            if not self._owns(db, job, 'processing'):
                return False
            db.execute('''UPDATE jobs SET status='drafted',result_json=?,input_tokens=?,
                output_tokens=?, cost_usd=cost_usd+?,response_id=?,
                updated_at=datetime('now') WHERE id=?''',
                (raw_json, response.input_tokens, response.output_tokens,
                 cost, response.response_id[:120], job.job_id))
            db.execute('''UPDATE processing_runs SET spent_usd=spent_usd+?,
                updated_at=datetime('now') WHERE id=?''', (cost, job.run_id))
        return True

    def _publish_draft(self, job: ClaimedJob, extra_issues: list[str] | None = None):
        """Code audit + provenance + FTS publication in ONE SQLite transaction.

        If this transaction aborts, persisted 'drafted' model result remains
        available to retry without another provider charge or API request.
        """
        with connection(self.db_file) as db, transaction(db):
            if not self._owns(db, job, 'drafted'):
                return
            saved = db.execute('SELECT result_json,input_sha256 FROM jobs WHERE id=?', (job.job_id,)).fetchone()
            source = db.execute('SELECT body_text,href FROM content_units WHERE id=?', (job.unit_id,)).fetchone()
            if source is None or sha256(source['body_text'].encode('utf-8')).hexdigest() != saved['input_sha256']:
                db.execute('''UPDATE jobs SET status='failed',error='Source changed during processing; start a new run',
                    lease_token=NULL,lease_until=NULL,finished_at=datetime('now') WHERE id=?''', (job.job_id,))
                _maybe_finalize(db, job.run_id)
                return
            try:
                payload = json.loads(saved['result_json'])
            except (ValueError, TypeError):
                payload = {}
            audit = audit_output(payload, source['body_text'])
            all_issues = [*(extra_issues or []), *audit.issues]
            passed = audit.passed and not extra_issues
            distilled_id = sha256((job.run_id + ':' + job.unit_id).encode('utf8')).hexdigest()
            previous = db.execute('SELECT status FROM distilled_units WHERE id=?', (distilled_id,)).fetchone()
            if previous is not None and previous['status'] == 'published':
                db.execute('''UPDATE jobs SET status='completed',lease_token=NULL,lease_until=NULL,
                    finished_at=datetime('now'),updated_at=datetime('now') WHERE id=?''', (job.job_id,))
                _maybe_finalize(db, job.run_id)
                return
            body_text = render_body(audit.payload) if audit.payload else json.dumps(payload, ensure_ascii=False)[:25000]
            title = audit.payload.title if audit.payload else job.title
            if previous:
                db.execute('''UPDATE distilled_units SET status='draft',title=?,body_text=?,
                    updated_at=datetime('now') WHERE id=?''', (title, body_text, distilled_id))
            else:
                db.execute('''INSERT INTO distilled_units(id,run_id,unit_id,status,title,body_text)
                    VALUES(?,?,?,'draft',?,?)''', (distilled_id, job.run_id, job.unit_id, title, body_text))
            rev = db.execute('''SELECT COALESCE(MAX(revision_no),0)+1 FROM distilled_revisions
                WHERE distilled_id=?''', (distilled_id,)).fetchone()[0]
            db.execute('''INSERT INTO distilled_revisions(id,distilled_id,revision_no,body_text,model,prompt_version)
                VALUES(?,?,?,?,?,?)''', (new_id(), distilled_id, rev, body_text, job.model, PROMPT_VERSION))
            db.execute('''INSERT INTO audit_results(id,distilled_id,audit_kind,passed,details_json)
                VALUES(?,?,'code',?,?)''', (new_id(), distilled_id, int(passed),
                    json.dumps({'issues': all_issues, 'prompt_version': PROMPT_VERSION,
                                'policy': 'code_only'}, ensure_ascii=False)))
            if passed and audit.payload:
                for i, claim in enumerate(audit.payload.claims):
                    claim_id = new_id()
                    db.execute('''INSERT INTO claims(id,distilled_id,text,ordinal)
                        VALUES(?,?,?,?)''', (claim_id, distilled_id, claim.text, i))
                    for ev in claim.evidence:
                        db.execute('''INSERT INTO evidence(id,claim_id,unit_id,quote,source_href)
                            VALUES(?,?,?,?,?)''', (new_id(), claim_id, job.unit_id, ev.quote, source['href']))
                db.execute('''UPDATE distilled_units SET status='published',updated_at=datetime('now')
                    WHERE id=?''', (distilled_id,))
            else:
                db.execute('''UPDATE distilled_units SET status='needs_review',updated_at=datetime('now')
                    WHERE id=?''', (distilled_id,))
            db.execute('''UPDATE jobs SET status=?,error=?,finished_at=datetime('now'),
                lease_token=NULL,lease_until=NULL, result_json=NULL,
                updated_at=datetime('now') WHERE id=?''',
                ('completed' if passed else 'needs_review', '; '.join(all_issues)[:500], job.job_id))
            _maybe_finalize(db, job.run_id)

    def _finalize_job(self, job: ClaimedJob, response: AIResponse | None,
                      issues: list[str], *, retryable: bool = False):
        # Backward-compatible internal façade used by integration tests.
        if response is None:
            self._record_provider_error(job, issues, retryable=retryable)
        elif self._persist_response(job, response):
            self._publish_draft(job, extra_issues=issues)

    def run_once(self) -> bool:
        job = self.claim()
        if job is None:
            return False
        if job.drafted:
            self._publish_draft(job)
            return True
        if len(job.body) > job.config['max_source_chars']:
            # Never truncate the source silently. This intentionally invalid
            # payload is quarantined by the code audit with no API charge.
            placeholder = AIResponse(payload={'title': job.title, 'summary': '',
                'key_points': [], 'claims': [], 'uncertainties': ['Oversized source unit']},
                response_id='', input_tokens=0, output_tokens=0)
            self._finalize_job(job, placeholder,
                [f'Source too large ({len(job.body)} chars > {job.config["max_source_chars"]}); split units before processing'])
            return True
        try:
            result = self.provider.generate(model=job.model, mode=job.mode,
                language=job.config['language'], title=job.title, href=job.href,
                source_body=job.body, max_output_tokens=job.config['max_output_tokens'])
        except ProviderError as exc:
            self._record_provider_error(job, [str(exc)], retryable=exc.retryable, pause_on_error=not exc.retryable)
        except Exception as exc:
            self._record_provider_error(job,
                [f'Unexpected provider error ({type(exc).__name__})'], retryable=True)
        else:
            self._finalize_job(job, result, [])
        return True


def get_knowledge(db_file: Path, distilled_id: str) -> dict | None:
    with connection(db_file) as db:
        row = db.execute('''SELECT d.*,r.model,r.mode,r.prompt_version,b.title book_title,b.id book_id,
            u.title source_title,u.href source_href,u.body_text source_body,u.id source_unit_id,
            f.original_filename FROM distilled_units d
            JOIN processing_runs r ON r.id=d.run_id
            JOIN content_units u ON u.id=d.unit_id
            JOIN editions e ON e.id=u.edition_id JOIN books b ON b.id=e.book_id
            JOIN source_files f ON f.id=u.source_file_id WHERE d.id=?''', (distilled_id,)).fetchone()
        if row is None:
            return None
        result = dict(row)
        claims = db.execute('SELECT * FROM claims WHERE distilled_id=? ORDER BY ordinal', (distilled_id,)).fetchall()
        result['claims'] = []
        for claim in claims:
            c = dict(claim)
            c['evidence'] = [dict(e) for e in db.execute('SELECT * FROM evidence WHERE claim_id=?', (c['id'],))]
            result['claims'].append(c)
        result['audits'] = [dict(a) for a in db.execute('''SELECT * FROM audit_results
            WHERE distilled_id=? ORDER BY created_at, rowid''', (distilled_id,))]
        result['revisions'] = [dict(rev) for rev in db.execute('''SELECT revision_no,created_at,model,prompt_version
            FROM distilled_revisions WHERE distilled_id=? ORDER BY revision_no DESC''', (distilled_id,))]
    return result
