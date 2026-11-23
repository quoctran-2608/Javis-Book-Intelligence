"""Deterministic M2 tests. Fake providers do NOT validate real model quality."""
from __future__ import annotations
from dataclasses import dataclass
import os
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from javis_book_intelligence.db import connection, transaction, backup, rebuild_fts
from javis_book_intelligence.service import import_epub_file, get_book
from javis_book_intelligence.engine import (
    create_run, get_run, Worker, control_run, raise_budget, retry_review, get_knowledge,
)
from javis_book_intelligence.providers import AIResponse, ProviderError, OpenAIResponsesProvider
from javis_book_intelligence.distillation import audit_output
from javis_book_intelligence.search import search
from javis_book_intelligence.web import create_app


class ScriptedProvider:
    def __init__(self, responses=None):
        self.responses = list(responses or [])
        self.calls = 0
        self.received = []

    def generate(self, **kwargs):
        self.calls += 1
        self.received.append(kwargs)
        if self.responses:
            item = self.responses.pop(0)
            if isinstance(item, Exception):
                raise item
            return item
        return success(kwargs['source_body'], kwargs['title'])


def success(body, title, *, quote=None, response_id='resp_1'):
    words = 'Vô thường' if 'Vô thường' in body else 'Tâm từ bi'
    quote = quote if quote is not None else words
    return AIResponse({
        'title': 'Bản chưng cất ' + title,
        'summary': 'Tóm lược có dẫn chứng chính xác. Hệ thống xuất bản sau audit.',
        'key_points': ['Tri thức kiểm tra tức thì'],
        'claims': [{'text': 'Khẳng định có nguồn: ' + words,
                    'evidence': [{'quote': quote}]}],
        'uncertainties': [],
    }, response_id, 250, 150)


def setup_run(workspace, example, **kwargs):
    db, store = workspace
    imported = import_epub_file(db, store, example, 'sample.epub')
    opts = {'budget_usd':5.0, 'input_price':1.0, 'output_price':2.0}
    opts.update(kwargs)
    run_id = create_run(db, source_file_id=imported['file_id'], mode='general', model='test-model', **opts)
    return db, imported, run_id


def test_incremental_publish_is_visible_before_next_unit(workspace, example):
    db, imported, run_id = setup_run(workspace, example)
    fake = ScriptedProvider()
    worker = Worker(db, fake)
    assert get_run(db, run_id)['summary']['pending'] == 2
    assert worker.run_once() is True
    one = get_run(db, run_id)
    assert one['state'] == 'processing'
    assert one['summary']['completed'] == 1 and one['summary']['pending'] == 1
    hits = search(db, 'Tri thức kiểm tra tức thì', scope='distilled')
    assert hits['total'] == 1 and hits['items'][0]['kind'] == 'distilled'
    detail = get_knowledge(db, hits['items'][0]['distilled_id'])
    assert detail['status'] == 'published'
    assert detail['claims'][0]['evidence'][0]['quote'] in detail['source_body']
    assert len(detail['audits']) == 1 and detail['audits'][0]['passed'] == 1
    assert fake.calls == 1
    assert worker.run_once() is True
    end = get_run(db, run_id)
    assert end['state'] == 'completed' and end['summary']['completed'] == 2
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 2
    assert search(db, 'Tri thức kiểm tra tức thì', scope='source')['total'] == 0
    assert search(db, 'Tri thức kiểm tra tức thì', scope='all')['total'] == 2
    assert end['spent_usd'] > 0


def test_invalid_quote_quarantined_then_revisioned_retry(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    fake = ScriptedProvider([success('Vô thường', 'bad', quote='Quote from nowhere')])
    worker = Worker(db, fake)
    worker.run_once()
    state = get_run(db, run_id)
    assert state['state'] == 'completed' and state['summary']['needs_review'] == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 0
    job = state['jobs'][0]
    detail = get_knowledge(db, job['distilled_id'])
    assert detail['status'] == 'needs_review' and not detail['audits'][0]['passed']
    retry_review(db, job['id'])
    assert get_run(db, run_id)['state'] == 'paused'
    control_run(db, run_id, 'resume')
    worker.run_once()
    revised = get_knowledge(db, job['distilled_id'])
    assert revised['status'] == 'published' and len(revised['revisions']) == 2
    assert len(revised['audits']) == 2
    assert revised['audits'][0]['passed'] == 0 and revised['audits'][1]['passed'] == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1
    assert len(revised['claims']) == 1  # no duplicate claims


def test_schema_invalid_never_publishes(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    fake = ScriptedProvider([AIResponse({'foo': 'bar'}, 'abc', 100, 50)])
    Worker(db, fake).run_once()
    run = get_run(db, run_id)
    assert run['summary']['needs_review'] == 1
    assert search(db, 'foo', scope='distilled')['total'] == 0
    assert get_knowledge(db, run['jobs'][0]['distilled_id'])['status'] == 'needs_review'


def test_retryable_error_with_bounded_retries_and_budget_accounting(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1, max_attempts=2)
    fake = ScriptedProvider([ProviderError('HTTP 429', retryable=True)])
    worker = Worker(db, fake)
    worker.run_once()
    state = get_run(db, run_id)
    assert state['summary']['retry_waiting'] == 1 and state['spent_usd'] == 0
    assert state['jobs'][0]['attempts'] == 1
    assert fake.calls == 1
    with connection(db) as con, transaction(con):
        con.execute('UPDATE jobs SET next_retry_at=0 WHERE id=?', (state['jobs'][0]['id'],))
    worker.run_once()
    state = get_run(db, run_id)
    assert state['summary']['completed'] == 1 and state['jobs'][0]['attempts'] == 2
    assert fake.calls == 2


def test_permanent_failure_and_recovery_after_manual_requeue(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    fake = ScriptedProvider([ProviderError('HTTP 401', retryable=False)])
    worker = Worker(db, fake)
    worker.run_once()
    run = get_run(db, run_id)
    assert run['state'] == 'failed' and run['summary']['failed'] == 1
    jobid = run['jobs'][0]['id']
    retry_review(db, jobid)
    control_run(db, run_id, 'resume')
    worker.run_once()
    assert get_run(db, run_id)['state'] == 'completed'


def test_pause_resume_and_stop_keep_pending_jobs(workspace, example):
    db, _, run_id = setup_run(workspace, example)
    fake = ScriptedProvider()
    worker = Worker(db, fake)
    control_run(db, run_id, 'pause')
    assert worker.run_once() is False and fake.calls == 0
    control_run(db, run_id, 'resume')
    worker.run_once()
    control_run(db, run_id, 'stop')
    assert worker.run_once() is False
    assert get_run(db, run_id)['summary']['completed'] == 1
    assert get_run(db, run_id)['summary']['pending'] == 1
    control_run(db, run_id, 'resume')
    worker.run_once()
    assert get_run(db, run_id)['state'] == 'completed'



def test_budget_preflight_pauses_before_external_request(workspace, example):
    db, _, run_id = setup_run(workspace, example, budget_usd=0.00001)
    fake = ScriptedProvider()
    worker = Worker(db, fake)
    assert not worker.run_once()
    run = get_run(db, run_id)
    assert run['state'] == 'paused' and 'Budget' in run['last_error']
    assert fake.calls == 0 and run['summary']['pending'] == 2
    raise_budget(db, run_id, 1.0)
    control_run(db, run_id, 'resume')
    assert worker.run_once()
    assert fake.calls == 1


def test_oversized_source_not_truncated_or_sent(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1, max_source_chars=100)
    with connection(db) as con, transaction(con):
        unit_id = con.execute('SELECT unit_id FROM jobs WHERE run_id=?', (run_id,)).fetchone()[0]
        con.execute('UPDATE content_units SET body_text=? WHERE id=?', ('Vô thường ' * 200, unit_id))
    fake = ScriptedProvider()
    worker = Worker(db, fake)
    worker.run_once()
    assert fake.calls == 0
    job = get_run(db, run_id)['jobs'][0]
    assert job['status'] == 'needs_review'
    assert 'Source too large' in job['error']
    assert search(db, 'Oversized', scope='distilled')['total'] == 0


def test_lease_claim_is_atomic_and_stale_worker_cannot_publish(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1, max_attempts=3)
    w1, w2 = Worker(db, ScriptedProvider()), Worker(db, ScriptedProvider())
    first = w1.claim(now=1000)
    assert first and w2.claim(now=1100) is None
    replacement = w2.claim(now=1301)
    assert replacement and replacement.job_id == first.job_id and replacement.token != first.token
    w1._finalize_job(first, success(first.body, first.title), [])
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 0
    w2._finalize_job(replacement, success(replacement.body, replacement.title), [])
    w2._finalize_job(replacement, success(replacement.body, replacement.title), [])
    assert get_run(db, run_id)['summary']['completed'] == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1
    with connection(db) as con:
        assert con.execute('SELECT COUNT(*) FROM distilled_revisions').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 1


def test_source_change_prevents_old_distillation_publication(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    w = Worker(db, ScriptedProvider())
    claim = w.claim()
    with connection(db) as con, transaction(con):
        con.execute('UPDATE content_units SET body_text=? WHERE id=?', ('Changed source', claim.unit_id))
    w._finalize_job(claim, success(claim.body, claim.title), [])
    job = get_run(db, run_id)['jobs'][0]
    assert job['status'] == 'failed' and 'Source changed' in job['error']
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 0


def test_transaction_rolls_back_partial_published_knowledge(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    w = Worker(db, ScriptedProvider())
    claim = w.claim()
    with connection(db) as con, transaction(con):
        con.execute('''CREATE TRIGGER abort_publish BEFORE UPDATE OF status ON distilled_units
            WHEN new.status='published' BEGIN SELECT RAISE(ABORT,'inject database failure'); END''')
    with pytest.raises(sqlite3.IntegrityError):
        w._finalize_job(claim, success(claim.body, claim.title), [])
    with connection(db) as con:
        assert con.execute('SELECT COUNT(*) FROM distilled_units').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM claims').fetchone()[0] == 0
        assert con.execute('SELECT COUNT(*) FROM audit_results').fetchone()[0] == 0
        assert con.execute('SELECT spent_usd FROM processing_runs WHERE id=?', (run_id,)).fetchone()[0] > 0
        assert con.execute('SELECT status FROM jobs WHERE id=?', (claim.job_id,)).fetchone()[0] == 'drafted'
        assert con.execute('SELECT result_json FROM jobs WHERE id=?', (claim.job_id,)).fetchone()[0] is not None
    with connection(db) as con, transaction(con):
        con.execute('DROP TRIGGER abort_publish')
    claimed_again = w.claim(now=time.time() + 301)
    assert claimed_again and claimed_again.drafted and claimed_again.token != claim.token
    charged = get_run(db, run_id)['spent_usd']
    w._publish_draft(claimed_again)
    assert get_run(db, run_id)['spent_usd'] == charged
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1


def test_backup_rebuild_and_source_distilled_separation(workspace, example, tmp_path):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    Worker(db, ScriptedProvider()).run_once()
    saved = tmp_path / 'db.bak'
    backup(db, saved)
    assert search(saved, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1
    rebuild_fts(saved)
    assert search(saved, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1
    with connection(saved) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert con.execute('PRAGMA foreign_key_check').fetchall() == []


def test_manual_invalid_input_and_inspection_are_safe(workspace, example):
    db, imported, run_id = setup_run(workspace, example)
    with pytest.raises(ValueError):
        create_run(db, source_file_id=imported['file_id'], mode='wrong', model='test')
    with pytest.raises(ValueError):
        create_run(db, source_file_id=imported['file_id'], mode='general', model='test', input_price=0)
    with pytest.raises(ValueError):
        create_run(db, source_file_id=imported['file_id'], mode='general', model='test', budget_usd=float('nan'))
    assert audit_output({'title':'valid','summary':'abc','key_points':['one'],
            'claims':[{'text':'ok', 'evidence':[{'quote':'invented'}]}],
            'uncertainties':[]}, 'true source').passed is False


def test_ui_start_status_search_and_origin_block(tmp_path, example, monkeypatch):
    fake = ScriptedProvider()
    app = create_app(tmp_path / 'web_m2', provider=fake, start_worker=False)
    with TestClient(app) as client:
        with example.open('rb') as f:
            client.post('/books/import', files={'files':('sample.epub',f,'application/epub+zip')})
        book_id = client.get('/api/books').json()['books'][0]['id']
        book = get_book(app.state.db_file, book_id)
        f_id = book['editions'][0]['files'][0]['id']
        assert 'Chưng cất EPUB' in client.get('/books/' + book_id).text
        cross = client.post('/processing/create', headers={'Origin':'https://attacker.example'},
                            data={'source_file_id': f_id,'model': 'gpt-test', 'budget_usd':1, 'input_price':1,'output_price':2})
        assert cross.status_code == 403
        r=client.post('/processing/create', data={
            'source_file_id':f_id,'model':'test-model','mode':'general',
            'language':'vi','budget_usd':'1','input_price':'1','output_price':'2',
            'unit_limit':'2'}, follow_redirects=False)
        assert r.status_code == 303
        run_id=r.headers['location'].rsplit('/',1)[-1]
        assert client.get('/processing/' + run_id).status_code == 200
        assert client.get('/api/processing/runs/'+run_id).json()['summary']['pending']==2
        app.state.worker.run_once()
        got=client.get('/api/search', params={'q':'Tri thức kiểm tra tức thì','scope':'distilled'}).json()
        assert got['total']==1 and got['items'][0]['detail_url'].startswith('/knowledge/')
        assert client.get(got['items'][0]['detail_url']).status_code==200
        assert 'CODE AUDIT ONLY' in client.get(got['items'][0]['detail_url']).text
        assert 'MILESTONE 2' in client.get('/processing').text


def test_openai_adapter_parses_responses_without_logging_secrets(monkeypatch):
    import json
    import httpx
    sent=[]
    output=success('Vô thường', 'sample')
    def handler(request):
        sent.append(json.loads(request.content))
        assert request.headers['Authorization'] == 'Bearer integration_test_key'
        return httpx.Response(200,json={
            'id':'resp_server','status':'completed',
            'usage':{'input_tokens':123,'output_tokens':45},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(output.payload)}]}],
        })
    transport=httpx.MockTransport(handler)
    orig_client=httpx.Client
    def mocked_client(**kwargs):
        return orig_client(transport=transport,**kwargs)
    monkeypatch.setenv('OPENAI_API_KEY','integration_test_key')
    monkeypatch.setattr(httpx, 'Client', mocked_client)
    adapter=OpenAIResponsesProvider()
    result=adapter.generate(model='test',mode='general',language='vi',title='Test',href='test.xhtml',
                            source_body='Vô thường',max_output_tokens=1200)
    assert result.input_tokens==123 and result.output_tokens==45
    assert sent[0]['store'] is False
    assert sent[0]['text']['format']['strict'] is True
    assert 'integration_test_key' not in str(sent)
    assert 'OPENAI_API_KEY' not in sent[0]


def test_drafted_checkpoint_survives_worker_restart_without_second_api_call(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    provider = ScriptedProvider()
    first_worker = Worker(db, provider)
    job = first_worker.claim(now=2000)
    model_result = provider.generate(model=job.model, mode=job.mode, language='vi',
                                     title=job.title, href=job.href, source_body=job.body,
                                     max_output_tokens=job.config['max_output_tokens'])
    assert first_worker._persist_response(job, model_result)
    before = get_run(db, run_id)
    assert before['summary']['drafted'] == 1 and provider.calls == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 0
    resumed = Worker(db, provider)
    # A second process can't steal a valid lease; it can resume after expiry.
    assert resumed.claim(now=2100) is None
    recovered = resumed.claim(now=2301)
    assert recovered and recovered.drafted
    resumed._publish_draft(recovered)
    after = get_run(db, run_id)
    assert after['state'] == 'completed' and after['spent_usd'] == before['spent_usd']
    assert provider.calls == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 1


def test_only_one_inflight_request_per_run_across_workers(workspace, example):
    db, _, run_id = setup_run(workspace, example)
    w1, w2 = Worker(db, ScriptedProvider()), Worker(db, ScriptedProvider())
    one = w1.claim()
    assert one and w2.claim() is None  # second unit waits for current unit
    w1._finalize_job(one, success(one.body, one.title), [])
    two = w2.claim()
    assert two and two.job_id != one.job_id


def test_host_header_prevents_dns_rebinding(tmp_path):
    app = create_app(tmp_path / 'web_host', start_worker=False)
    with TestClient(app) as client:
        assert client.get('/api/health', headers={'Host':'evil.example'}).status_code == 400
        assert client.get('/api/health').status_code == 200


def test_existing_m1_database_is_upgraded_in_place(tmp_path, example):
    from javis_book_intelligence.db import initialize, MIGRATIONS
    legacy_db = tmp_path / 'upgrade.db'
    import sqlite3
    with sqlite3.connect(legacy_db) as con:
        con.execute("CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')))")
        for version in ('0001_library', '0002_future_distillation_schema'):
            con.executescript('BEGIN IMMEDIATE;\n' + (MIGRATIONS / (version + '.sql')).read_text() +
                              f"\nINSERT INTO schema_migrations(version) VALUES('{version}');\nCOMMIT;")
    store = tmp_path / 'epubs'
    saved = import_epub_file(legacy_db, store, example, 'sample.epub')
    before = search(legacy_db, 'vô thường', scope='source')
    initialize(legacy_db)
    assert search(legacy_db, 'vô thường', scope='source')['total'] == before['total'] == 1
    with connection(legacy_db) as db:
        versions = [r[0] for r in db.execute('SELECT version FROM schema_migrations ORDER BY version')]
        assert len(versions) == 3
        assert db.execute('SELECT sha256 FROM source_files WHERE id=?', (saved['file_id'],)).fetchone()[0]


def test_nonretryable_provider_error_pauses_other_units(workspace, example):
    db, _, run_id = setup_run(workspace, example)
    provider = ScriptedProvider([ProviderError('OpenAI API returned HTTP 401', retryable=False)])
    worker = Worker(db, provider)
    worker.run_once()
    state = get_run(db, run_id)
    assert state['state'] == 'paused'
    assert state['summary']['failed'] == 1 and state['summary']['pending'] == 1
    assert worker.run_once() is False


def test_dictionary_prompt_honors_mode_and_avoids_entries_assumption(workspace, example):
    from javis_book_intelligence.distillation import instructions
    assert 'dictionary entry' in instructions('dictionary','vi')
    assert 'separation' in instructions('dictionary','vi')
    assert 'argument and context' in instructions('general','vi')


def test_published_ft_index_updates_without_stale_revision(workspace, example):
    db, _, run_id = setup_run(workspace, example, unit_limit=1)
    Worker(db, ScriptedProvider()).run_once()
    did = get_run(db, run_id)['jobs'][0]['distilled_id']
    with connection(db) as con, transaction(con):
        con.execute('UPDATE distilled_units SET body_text=? WHERE id=?', ('newterm-xylophone chỉ mục mới', did))
    assert search(db, 'xylophone', scope='distilled')['total'] == 1
    assert search(db, 'Tri thức kiểm tra tức thì', scope='distilled')['total'] == 0
    rebuild_fts(db)
    assert search(db, 'xylophone', scope='distilled')['total'] == 1
    with connection(db) as con, transaction(con):
        con.execute("UPDATE distilled_units SET status='needs_review' WHERE id=?", (did,))
    assert search(db, 'xylophone', scope='distilled')['total'] == 0
