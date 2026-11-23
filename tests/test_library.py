from pathlib import Path
import sqlite3
import zipfile
import pytest
from javis_book_intelligence.db import connection, initialize, backup, rebuild_fts, transaction
from javis_book_intelligence.epub import EpubError, parse_epub
from javis_book_intelligence.service import import_epub_file, get_book, get_unit, update_book_metadata
from javis_book_intelligence.search import search, make_match
from conftest import write_epub


def test_migrations_are_idempotent(workspace):
    db, _ = workspace
    initialize(db)
    with connection(db) as con:
        assert [r[0] for r in con.execute('SELECT version FROM schema_migrations ORDER BY version')] == [
            '0001_library','0002_future_distillation_schema','0003_incremental_engine']
        assert con.execute('PRAGMA foreign_key_check').fetchall() == []


def test_import_epub_and_metadata(workspace, example):
    db, store = workspace
    imported = import_epub_file(db,store,example,'sample.epub')
    assert imported['status'] == 'imported' and imported['units'] == 2
    book = get_book(db, imported['book_id'])
    assert book['title'] == 'Tri thức mẫu'
    assert book['editions'][0]['authors'] == ['Tác giả mẫu']
    assert book['editions'][0]['publication_year'] == 2023
    assert book['editions'][0]['units'][1]['title'] == 'Chương Hai'
    unit = get_unit(db,book['editions'][0]['units'][0]['id'])
    assert unit['href'] == 'OEBPS/chapter1.xhtml'
    assert 'Vô thường' in unit['body_text']
    assert (store / (imported['file_id'] + '.epub')).exists() is False  # content addressed by SHA


def test_duplicate_sha_does_not_reimport(workspace, example):
    db, store = workspace
    original = import_epub_file(db,store,example,'one.epub')
    duplicate = import_epub_file(db,store,example,'renamed.epub')
    assert duplicate['status'] == 'duplicate' and duplicate['book_id'] == original['book_id']
    with connection(db) as con:
        assert con.execute('SELECT COUNT(*) FROM source_files').fetchone()[0] == 1
        assert con.execute('SELECT COUNT(*) FROM content_units').fetchone()[0] == 2


def test_editions_not_auto_merged(workspace, example, tmp_path):
    db, store = workspace
    a = import_epub_file(db,store,example,'sample.epub')
    bfile = write_epub(tmp_path/'other.edition.epub',intro='Một phiên bản khác về vô thường.')
    b = import_epub_file(db,store,bfile,'other.edition.epub',existing_book_id=a['book_id'])
    assert b['book_id'] == a['book_id'] and b['edition_id'] != a['edition_id']
    assert len(get_book(db,a['book_id'])['editions']) == 2


def test_fallback_separate_work_when_no_book_selected(workspace,example,tmp_path):
    db, store = workspace
    a = import_epub_file(db,store,example,'sample.epub')
    second = write_epub(tmp_path/'copy.edition.epub',intro='Bản dịch hoàn toàn khác.')
    b = import_epub_file(db,store,second,'copy.edition.epub')
    assert b['book_id'] != a['book_id']


def test_search_keyword_phrase_prefix_and_vietnamese(workspace,example):
    db, store = workspace
    import_epub_file(db,store,example,'sample.epub')
    assert search(db,'vô thường')['total'] == 1
    assert search(db,'vo thuong')['total'] == 1   # FTS5 remove_diacritics=2
    assert search(db,'Vô thường là bản chất',mode='phrase')['total'] == 1
    assert search(db,'thường là vô',mode='phrase')['total'] == 0
    assert search(db,'thư',mode='prefix')['total'] >= 1
    assert search(db,'Tâm từ bi',mode='phrase')['total'] == 1
    assert search(db,'" OR * {',mode='keyword')['total'] == 0
    assert make_match('" OR * {', 'keyword') == '"OR"'


def test_search_updates_and_rebuild(workspace,example):
    db, store = workspace
    imported = import_epub_file(db,store,example,'sample.epub')
    unitid = get_book(db,imported['book_id'])['editions'][0]['units'][0]['id']
    with connection(db) as con, transaction(con):
        con.execute('UPDATE content_units SET body_text=? WHERE id=?',('Mẫu thông tin quasar-unique.',unitid))
    assert search(db,'quasar')['total'] == 1
    assert search(db,'vô thường')['total'] == 0
    rebuild_fts(db)
    assert search(db,'quasar')['total'] == 1
    with connection(db) as con, transaction(con):
        con.execute('DELETE FROM content_units WHERE id=?',(unitid,))
    assert search(db,'quasar')['total'] == 0


def test_metadata_edit_and_rollback(workspace,example):
    db, store = workspace
    i = import_epub_file(db,store,example,'sample.epub')
    vals = dict(title='Tên đã sửa',subtitle='Phụ đề',description='Ghi chú',tags='Phật học, Triết học',
                edition_id=i['edition_id'],authors='Tác giả mới, Dịch giả A',language='en',
                publisher='NXB mới',publication_year='2024',isbn='123',edition_label='Bản mới')
    update_book_metadata(db,i['book_id'],**vals)
    b = get_book(db,i['book_id'])
    assert b['title']=='Tên đã sửa' and b['tags']==['Phật học','Triết học']
    assert len(b['editions'][0]['authors'])==2
    with pytest.raises(ValueError):
        update_book_metadata(db,i['book_id'],**{**vals,'title':'Sai','publication_year':'3001'})
    assert get_book(db,i['book_id'])['title']=='Tên đã sửa'


def test_fk_and_transaction_are_robust(workspace):
    db, _ = workspace
    with pytest.raises(sqlite3.IntegrityError):
        with connection(db) as con, transaction(con):
            con.execute('INSERT INTO editions(id,book_id) VALUES(?,?)',('fake','notthere'))
    with connection(db) as con:
        assert con.execute('SELECT COUNT(*) FROM editions').fetchone()[0] == 0


def test_backup_restore(workspace,example,tmp_path):
    db,store=workspace
    import_epub_file(db,store,example,'sample.epub')
    dest=tmp_path/'backup.db'
    backup(db,dest)
    assert search(dest,'từ bi')['total']==1
    with connection(dest) as con:
        assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'


def test_rejects_unsafe_zip_paths(tmp_path):
    path=tmp_path/'bad.epub'
    with zipfile.ZipFile(path,'w') as z:
        z.writestr('../traversal','bad')
        z.writestr('META-INF/container.xml','<container/>')
    with pytest.raises(EpubError,match='unsafe'):
        parse_epub(path)


def test_future_distilled_index_only_published(workspace,example):
    db,store=workspace
    i=import_epub_file(db,store,example,'sample.epub')
    unit_id = get_book(db,i['book_id'])['editions'][0]['units'][0]['id']
    with connection(db) as con, transaction(con):
        con.execute("INSERT INTO processing_runs(id,source_file_id,mode,model,prompt_version) VALUES(?,?,?,?,?)",
                    ('run',i['file_id'],'general','test-no-ai','v0'))
        con.execute("INSERT INTO distilled_units(id,run_id,unit_id,status,title,body_text) VALUES(?,?,?,?,?,?)",
                    ('dist','run',unit_id,'draft','Sơ bộ','Bản nháp kiwi-xyz'))
    with connection(db) as con:
        assert con.execute("SELECT COUNT(*) FROM distilled_fts WHERE distilled_fts MATCH 'kiwi'").fetchone()[0]==0
        with transaction(con):
            con.execute("UPDATE distilled_units SET status='published' WHERE id='dist'")
        assert con.execute("SELECT COUNT(*) FROM distilled_fts WHERE distilled_fts MATCH 'kiwi'").fetchone()[0]==1
        with transaction(con):
            con.execute("UPDATE distilled_units SET status='needs_review' WHERE id='dist'")
        assert con.execute("SELECT COUNT(*) FROM distilled_fts WHERE distilled_fts MATCH 'kiwi'").fetchone()[0]==0


def test_incremental_fts_visibility_is_transactional(workspace, example):
    """Readers can search committed units while another write is uncommitted."""
    db, store = workspace
    i = import_epub_file(db,store,example,'sample.epub')
    with connection(db) as writer:
        writer.execute('BEGIN IMMEDIATE')
        writer.execute("""INSERT INTO content_units
            (id,edition_id,source_file_id,spine_index,title,href,body_text,char_count)
            VALUES(?,?,?,?,?,?,?,?)""",('next_unit',i['edition_id'],i['file_id'],99,
                    'Bổ sung','new.xhtml','Từ khóa onlyaftercommit',len('Từ khóa onlyaftercommit')))
        assert search(db,'vô thường')['total'] == 1
        assert search(db,'onlyaftercommit')['total'] == 0
        writer.execute('COMMIT')
    assert search(db,'onlyaftercommit')['total'] == 1
    # A new connection can see it without rebuilding the index.
    with connection(db) as fresh:
        assert fresh.execute("SELECT COUNT(*) FROM source_fts WHERE source_fts MATCH 'onlyaftercommit'").fetchone()[0] == 1


def test_cross_book_search_and_scoping(workspace,tmp_path):
    db, store = workspace
    a_file = write_epub(tmp_path/'a.epub',title='Sách A',intro='Định nghĩa riêng biệt về thiền định.')
    b_file = write_epub(tmp_path/'b.epub',title='Sách B',intro='Luận điểm khác về thiền định.')
    c_file = write_epub(tmp_path/'c.epub',title='Sách C',intro='Khảo sát địa chất cổ đại.',second='Bằng chứng địa chất.')
    a = import_epub_file(db,store,a_file,'a.epub')
    b = import_epub_file(db,store,b_file,'b.epub')
    c = import_epub_file(db,store,c_file,'c.epub')
    all_results=search(db,'thiền định')
    assert all_results['total']==2
    assert {x['book_id'] for x in all_results['items']}=={a['book_id'],b['book_id']}
    assert search(db,'thiền định',book_id=a['book_id'])['total']==1
    assert search(db,'thiền định',book_id=c['book_id'])['total']==0
    assert search(db,'thiền định',page=2,per_page=1)['total']==2
    assert len(search(db,'thiền định',page=2,per_page=1)['items'])==1


def test_invalid_epub_never_creates_partial_records(workspace,tmp_path):
    db,store=workspace
    bad=tmp_path/'invalid.epub'
    bad.write_bytes(b'not a valid epub')
    with pytest.raises(EpubError):
        import_epub_file(db,store,bad,'invalid.epub')
    with connection(db) as con:
        assert con.execute('SELECT COUNT(*) FROM books').fetchone()[0]==0
        assert con.execute('SELECT COUNT(*) FROM source_files').fetchone()[0]==0
    assert not list(store.glob('*.epub'))
