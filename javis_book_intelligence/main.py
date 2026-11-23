"""Entrypoint. Binds ONLY to localhost (single-user desktop MVP)."""
from .web import create_app
import uvicorn


def main():
    print('Javis Book Intelligence (M1): http://127.0.0.1:8765')
    print('Press Ctrl+C to stop. Book data is stored in JAVIS_DATA_DIR or ~/.javis_book_intelligence')
    uvicorn.run(create_app(), host='127.0.0.1', port=8765, log_level='info')


if __name__ == '__main__':
    main()
