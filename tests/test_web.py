from fastapi.testclient import TestClient
from javis_book_intelligence.service import get_book


def test_browser_upload_and_search(app,example):
    with TestClient(app) as client:
        main = client.get('/')
        assert main.status_code == 200 and 'Nhập EPUB' in main.text
        with example.open('rb') as f:
            response = client.post('/books/import', files={'files':('sample.epub',f,'application/epub+zip')}, follow_redirects=True)
        assert response.status_code == 200
        assert 'Đã nhập 1 EPUB' in response.text
        health=client.get('/api/health').json()
        assert health['source_units']==2
        hits=client.get('/api/search',params={'q':'vô thường'}).json()
        assert hits['total']==1
        assert '⟦Vô⟧ ⟦thường⟧' in hits['items'][0]['snippet']
        assert client.get('/units/'+hits['items'][0]['unit_id']).status_code==200
        assert 'SQLITE FTS5' in client.get('/search').text
        assert client.get('/api/search',params={'q':'foo','mode':'bad'}).status_code==422
        assert client.get('/api/search',params={'q':'foo','per_page':100}).status_code==422


def test_form_metadata(app,example):
    with TestClient(app) as client:
        with example.open('rb') as f:
            client.post('/books/import',files={'files':('sample.epub',f,'application/epub+zip')})
        book=client.get('/api/books').json()['books'][0]
        b=get_book(app.state.db_file,book['id'])
        edition=b['editions'][0]
        response=client.post('/books/'+book['id']+'/metadata',data={
            'title':'Tên đã cập nhật','edition_id':edition['id'],'authors':'Người viết',
            'tags':'Thuật ngữ, Học thuật','language':'vi','publication_year':'2025'},follow_redirects=True)
        assert response.status_code==200 and 'Tên đã cập nhật' in response.text
        assert get_book(app.state.db_file,book['id'])['tags']==['Học thuật','Thuật ngữ']
        response=client.get('/files/'+edition['files'][0]['id'])
        assert response.status_code==200 and response.content[:2]==b'PK'


def test_multi_epub_http_upload(app,example,tmp_path):
    from conftest import write_epub
    other=write_epub(tmp_path/'second.epub',title='Quyển khác',intro='Địa lý phương Đông.')
    with TestClient(app) as client,example.open('rb') as f1,other.open('rb') as f2:
        r=client.post('/books/import',files=[('files',('sample.epub',f1,'application/epub+zip')),
                                            ('files',('second.epub',f2,'application/epub+zip'))],follow_redirects=True)
        assert r.status_code==200
        assert 'Đã nhập 2 EPUB' in r.text
        assert len(client.get('/api/books').json()['books'])==2
