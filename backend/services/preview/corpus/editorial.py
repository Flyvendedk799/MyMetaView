"""Human editorial evaluations complement pixel checks; missing reviews never pass."""
from collections import defaultdict

DIMENSIONS = ('accuracy', 'relevance', 'brand_fidelity', 'small_size_readability')


def summarize_reviews(rows):
    rows = list(rows)
    groups = defaultdict(list)
    seen = set()
    for row in rows:
        if not row.get('reviewer') or not row.get('reviewed_at'):
            raise ValueError('Every evaluation requires a reviewer and timestamp.')
        key = (row['url'], row['revision'], row['reviewer'])
        if key in seen:
            raise ValueError('Duplicate evaluation for URL, revision and reviewer.')
        seen.add(key)
        if any(type(row.get(d)) is not int or not 1 <= row[d] <= 5 for d in DIMENSIONS):
            raise ValueError('All four dimensions require an integer score from 1 to 5.')
        if row.get('comparison') not in ('better', 'same', 'worse', 'no_original'):
            raise ValueError('Compare with the original card, or explicitly record no_original.')
        if type(row.get('needs_edit')) is not bool:
            raise ValueError('Record whether the card needs editing.')
        groups[row.get('page_type', 'unknown')].append(row)
    def stats(items):
        compared = [r for r in items if r['comparison'] != 'no_original']
        return {
            'review_count': len(items),
            'publishable_rate': sum(r['accuracy'] == 5 and all(r[d] >= 4 for d in DIMENSIONS)
                                    and not r['needs_edit'] for r in items) / len(items) if items else None,
            'beats_original_rate': sum(r['comparison'] == 'better' for r in compared) / len(compared) if compared else None,
            'mean_scores': {d: sum(r[d] for r in items)/len(items) if items else None for d in DIMENSIONS},
        }
    return {'overall': stats(rows), 'by_page_type': {k: stats(v) for k,v in groups.items()}}
