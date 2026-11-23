from pathlib import Path
import zipfile
import pytest
from javis_book_intelligence.web import create_app


def write_epub(path: Path, title='Tri thức mẫu', author='Tác giả mẫu', intro='Vô thường là bản chất của các pháp.',
               second='Tâm từ bi giúp con người hiểu nhau hơn.', language='vi'):
    """Create a real small DRM-free EPUB, not a fake Python parser output."""
    container = '''<?xml version="1.0" encoding="utf-8"?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container" version="1.0">
    <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>'''
    opf = f'''<?xml version="1.0" encoding="utf-8"?>
    <package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="bookid">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
      <dc:title>{title}</dc:title><dc:creator>{author}</dc:creator><dc:language>{language}</dc:language>
      <dc:publisher>Nhà xuất bản Thử nghiệm</dc:publisher><dc:date>2023-04-01</dc:date>
      <dc:identifier id="bookid">ISBN 978-1-234-56789-0</dc:identifier>
    </metadata>
    <manifest><item id="c1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
    <item id="c2" href="chapter2.xhtml" media-type="application/xhtml+xml"/></manifest>
    <spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>'''
    h1 = f'<html><head><title>title</title></head><body><h1>Chương Một</h1><p>{intro}</p></body></html>'
    h2 = f'<html><body><h2>Chương Hai</h2><p>{second}</p></body></html>'
    with zipfile.ZipFile(path, 'w') as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', container)
        z.writestr('OEBPS/content.opf', opf)
        z.writestr('OEBPS/chapter1.xhtml', h1)
        z.writestr('OEBPS/chapter2.xhtml', h2)
    return path


@pytest.fixture
def workspace(tmp_path):
    from javis_book_intelligence.db import initialize
    db = tmp_path / 'data' / 'library.db'
    initialize(db)
    store = tmp_path / 'data' / 'epubs'
    store.mkdir(parents=True)
    return db, store

@pytest.fixture
def app(tmp_path):
    return create_app(tmp_path / 'webdata')

@pytest.fixture
def example(tmp_path):
    return write_epub(tmp_path / 'sample.epub')
