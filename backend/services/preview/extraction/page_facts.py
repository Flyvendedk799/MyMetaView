"""Page-specific facts with provenance, used as constraints on authored copy."""
import json
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urldefrag

TYPE_FIELDS = {
    'Product': ('product', ('name', 'description', 'sku', 'offers', 'aggregateRating')),
    'Article': ('article', ('headline', 'description', 'author', 'datePublished')),
    'NewsArticle': ('article', ('headline', 'description', 'author', 'datePublished')),
    'BlogPosting': ('article', ('headline', 'description', 'author', 'datePublished')),
    'Person': ('profile', ('name', 'description', 'jobTitle', 'worksFor')),
    'Event': ('event', ('name', 'description', 'startDate', 'endDate', 'location', 'offers')),
}


def extract_page_facts(html, url):
    soup = BeautifulSoup(html or '', 'html.parser')
    canonical = soup.find('link', rel='canonical')
    canonical_url = urljoin(url, canonical.get('href', '')) if canonical else url
    # Canonical identity is accepted only within this site by the coverage layer.
    candidates = []
    def walk(value, path):
        if isinstance(value, list):
            for i, child in enumerate(value): walk(child, f'{path}[{i}]')
        elif isinstance(value, dict):
            types = value.get('@type', [])
            for typ in ([types] if isinstance(types, str) else types):
                if typ in TYPE_FIELDS: candidates.append((typ, value, path))
            for key in ('@graph', 'mainEntity'):
                if key in value: walk(value[key], f'{path}.{key}')
    for i, script in enumerate(soup.find_all('script', type='application/ld+json')):
        try: walk(json.loads(script.string or script.get_text()), f'jsonld[{i}]')
        except (ValueError, TypeError): pass
    h1 = soup.find('h1')
    title = h1.get_text(' ', strip=True) if h1 else (soup.title.get_text(' ', strip=True) if soup.title else '')
    def matches(item):
        entity = item[1]
        identity = entity.get('url') or entity.get('mainEntityOfPage') or entity.get('@id')
        if isinstance(identity, dict): identity = identity.get('@id')
        return bool(identity and urldefrag(urljoin(url, str(identity)))[0] in (urldefrag(url)[0], urldefrag(canonical_url)[0]))
    selected = next((c for c in candidates if matches(c)), None)
    if selected is None:
        selected = next((c for c in candidates if str(c[1].get('headline') or c[1].get('name') or '').casefold() == title.casefold() and title), None)
    # An ambiguous list of products/people is not a detail page.
    if selected is None and len(candidates) == 1:
        selected = candidates[0]
    fields = {}
    kind = 'landing'
    if selected:
        typ, entity, path = selected
        kind, keys = TYPE_FIELDS[typ]
        for key in keys:
            if entity.get(key) is not None:
                fields[key] = {'value': entity[key], 'source': f'{path}.{key}', 'confidence': 'structured'}
        title = str(entity.get('headline') or entity.get('name') or title)
    for element in soup(['script', 'style', 'nav', 'footer', 'header']): element.decompose()
    visible = soup.get_text(' ', strip=True)
    description_tag = soup.find('meta', attrs={'name': 'description'})
    description = str(fields.get('description', {}).get('value') or (description_tag.get('content', '') if description_tag else ''))
    return {'page_type': kind, 'title': title, 'description': description, 'canonical_url': canonical_url,
            'language': (soup.html.get('lang') if soup.html else None), 'fields': fields,
            'visible_text': visible[:20000]}


def grounded_copy(result, facts):
    """Reject unsupported numeric claims; proof must be verbatim evidence.

    This is a conservative deterministic check, not a general factuality judge.
    Human editorial evaluation still covers semantic claims.
    """
    evidence = facts['visible_text'] + ' ' + json.dumps(facts['fields'], ensure_ascii=False)
    numbers = set(re.findall(r'\d+(?:[.,]\d+)*', evidence))
    def supported(text): return set(re.findall(r'\d+(?:[.,]\d+)*', text or '')) <= numbers
    if not supported(result.title): result.title = facts['title'] or result.title
    if not supported(result.subtitle): result.subtitle = facts['description'] or None
    if not supported(result.description): result.description = facts['description']
    normalize = lambda text: re.sub(r'\W+', '', text or '').casefold()
    if result.proof and normalize(result.proof) not in normalize(evidence):
        result.proof = None
        result.credibility_items = []
    result.variants = [v for v in result.variants if supported(v.get('title')) and supported(v.get('subtitle'))]
    if facts['fields']:
        result.blueprint['template_type'] = facts['page_type']
    return result
