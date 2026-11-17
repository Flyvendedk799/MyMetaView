"""Create a human review packet from corpus records, or score completed reviews.

python -m backend.scripts.preview_engine.editorial_review packet records.json output-dir
python -m backend.scripts.preview_engine.editorial_review score reviews.json --min-reviews 20 --min-rate .9
"""
import argparse
import html
import json
from pathlib import Path
from backend.services.preview.corpus.editorial import DIMENSIONS, summarize_reviews


def packet(records, directory):
    directory.mkdir(parents=True, exist_ok=True)
    reviews, cards = [], []
    for row in records:
        reviews.append(dict(url=row['url'], revision=row.get('commit', row.get('revision', 'record-commit-here')),
            page_type=row.get('expected_template_type', 'unknown'), reviewer=None, reviewed_at=None,
            **{d: None for d in DIMENSIONS}, comparison=None, needs_edit=None, notes=''))
        def esc(value): return html.escape(str(value or ''), quote=True)
        cards.append(f"<article><h2>{esc(row['url'])}</h2><p>Generated · actual share size</p>"
                     f"<img width='400' src='{esc(row.get('primary_image_url'))}'>"
                     + (f"<p>Original</p><img width='400' src='{esc(row['original_image_url'])}'>" if row.get('original_image_url') else '<p>Original not captured. Inspect the source page before scoring.</p>')
                     + f"<p><a href='{esc(row['url'])}'>Inspect source facts and brand</a></p></article>")
    (directory/'reviews.json').write_text(json.dumps(reviews, indent=2))
    (directory/'review.html').write_text('<!doctype html><meta charset="utf-8"><title>Card quality review</title><style>body{font:16px system-ui;max-width:1000px;margin:40px auto}article{border-bottom:1px solid #ccc;padding:24px}img{max-width:100%}</style><h1>Card quality review</h1><p>Rate each dimension 1–5. Accuracy must be 5, other dimensions at least 4, and no editing needed to count as publishable.</p>'+''.join(cards))


def main():
    parser=argparse.ArgumentParser()
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('packet');p.add_argument('records');p.add_argument('output')
    p=sub.add_parser('score');p.add_argument('reviews');p.add_argument('--min-reviews',type=int,default=20);p.add_argument('--min-rate',type=float,default=.9)
    args=parser.parse_args()
    if args.command == 'packet':
        records=json.loads(Path(args.records).read_text())
        packet(records.get('records', records) if isinstance(records,dict) else records,Path(args.output))
        return
    result=summarize_reviews(json.loads(Path(args.reviews).read_text()))
    print(json.dumps(result,indent=2))
    overall=result['overall']
    if overall['review_count'] < args.min_reviews or (overall['publishable_rate'] or 0) < args.min_rate:
        raise SystemExit(1)

if __name__ == '__main__': main()
