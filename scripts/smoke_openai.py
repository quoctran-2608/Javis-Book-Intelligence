"""Opt-in ONE-UNIT real OpenAI API smoke test; can incur actual API charges.

This verifies API connectivity and database workflow, not semantic quality.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from javis_book_intelligence.db import initialize
from javis_book_intelligence.service import import_epub_file
from javis_book_intelligence.engine import create_run, Worker, get_run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epub', type=Path, required=True, help='DRM-free EPUB you have rights to process')
    parser.add_argument('--model', required=True, help='Supported OpenAI Responses API model ID')
    parser.add_argument('--input-price', type=float, required=True, help='Verified USD per million input tokens')
    parser.add_argument('--output-price', type=float, required=True, help='Verified USD per million output tokens')
    parser.add_argument('--budget', type=float, default=0.50, help='Budget preflight cap in USD')
    parser.add_argument('--confirm-send-to-openai', action='store_true',
                        help='Explicitly authorize sending one complete EPUB XHTML unit to OpenAI')
    parser.add_argument('--data-dir', type=Path, help='Persistent local directory; defaults to temp (deleted after run)')
    args = parser.parse_args()
    if not args.confirm_send_to_openai:
        parser.error('Use --confirm-send-to-openai only if you have rights to send this EPUB to an API')
    if not os.environ.get('OPENAI_API_KEY'):
        parser.error('OPENAI_API_KEY must be set in your local environment')

    def perform(data_dir: Path):
        db = data_dir / 'library.db'
        initialize(db)
        uploaded = import_epub_file(db, data_dir / 'epubs', args.epub, args.epub.name)
        run_id = create_run(db, source_file_id=uploaded['file_id'], mode='general', model=args.model,
                            unit_limit=1, budget_usd=args.budget,
                            input_price=args.input_price, output_price=args.output_price)
        Worker(db).run_once()
        run = get_run(db, run_id)
        print('Run:', run_id, 'status:', run['state'], 'summary:', run['summary'])
        print('Recorded estimated-price cost (USD):', round(run['spent_usd'], 6))
        print('Model output is NOT independently validated for semantic accuracy.')
        if run['summary']['completed'] != 1:
            raise SystemExit('Smoke test did not publish an audited unit; inspect its job status.')

    if args.data_dir:
        target = args.data_dir.expanduser().resolve()
        target.mkdir(parents=True, exist_ok=True)
        perform(target)
    else:
        with TemporaryDirectory(prefix='javis-m2-real-api-') as folder:
            perform(Path(folder))


if __name__ == '__main__':
    main()
