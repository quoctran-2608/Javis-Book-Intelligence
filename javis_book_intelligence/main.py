"""Start the local-only FastAPI application. Never bind publicly by default."""
from .web import create_app
import uvicorn


def main():
    print('Javis Book Intelligence (Milestone 2): http://127.0.0.1:8765')
    print('Data: JAVIS_DATA_DIR or ~/.javis_book_intelligence')
    print('Optional AI: OPENAI_API_KEY must be set in the local environment')
    uvicorn.run(create_app(), host='127.0.0.1', port=8765, log_level='info')


if __name__ == '__main__':
    main()
