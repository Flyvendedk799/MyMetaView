"""Verify the bytes social crawlers receive, independently of snippet heartbeats."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from io import BytesIO
from PIL import Image
from backend.services.preview.net.session import fetch

CRAWLERS = {
    "Facebook": "facebookexternalhit/1.1 (+http://www.facebook.com/externalhit_uatext.php)",
    "LinkedIn": "LinkedInBot/1.0",
    "X": "Twitterbot/1.0",
}


class HeadTags(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.values = {}
        self.in_head = False

    def handle_starttag(self, tag, attrs):
        if tag == 'head':
            self.in_head = True
        if tag != 'meta' or not self.in_head:
            return
        attrs = dict(attrs)
        key = attrs.get('property', attrs.get('name', '')).lower()
        if key.startswith(('og:', 'twitter:')):
            self.values.setdefault(key, []).append(attrs.get('content', '').strip())

    def handle_endtag(self, tag):
        if tag == 'head':
            self.in_head = False


def check_crawler(url, expected_title, expected_image, name, user_agent):
    issues = []
    page = fetch(url, headers={'User-Agent': user_agent}, timeout=8, max_bytes=512*1024)
    if not page.ok:
        return {'platform': name, 'ready': False, 'issues': [f'Page unavailable (HTTP {page.status}).']}
    tags = HeadTags()
    tags.feed(page.text)
    for key in ('og:title', 'og:image'):
        values = tags.values.get(key, [])
        if not values or not values[0]:
            issues.append(f'Missing {key} in the initial page head.')
        elif len(set(values)) > 1:
            issues.append(f'Conflicting {key} tags. Remove the older integration tags.')
    title = (tags.values.get('og:title') or [''])[0]
    image_url = (tags.values.get('og:image') or [''])[0]
    if title and title != expected_title:
        issues.append('The served title differs from your published card.')
    if image_url and image_url != expected_image:
        issues.append('The served image differs from your published card.')
    if name == 'X':
        for key, expected in [('twitter:title', expected_title), ('twitter:image', expected_image)]:
            values = tags.values.get(key, [])
            if values and (len(set(values)) > 1 or values[0] != expected):
                issues.append(f'{key} overrides your published card.')
    dimensions = None
    if image_url:
        image = fetch(image_url, headers={'User-Agent': user_agent}, timeout=8, max_bytes=8*1024*1024)
        try:
            if not image.ok or not image.content_type.startswith('image/'):
                raise ValueError('unavailable')
            with Image.open(BytesIO(image.content)) as decoded:
                dimensions = list(decoded.size)
                decoded.verify()
            if dimensions[0] < 200 or dimensions[1] < 200:
                issues.append('The image is too small for a dependable share card (minimum 200×200).')
        except Exception:
            issues.append('The crawler could not download a valid image.')
    return {'platform': name, 'ready': not issues, 'issues': issues,
            'image_url': image_url, 'dimensions': dimensions, 'checked_url': page.url}


def check_delivery(url, title, image):
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(check_crawler, url, title, image, name, ua) for name, ua in CRAWLERS.items()]
        checks = [f.result() for f in futures]
    return {'ready': all(c['ready'] for c in checks), 'checks': checks,
            'message': 'Crawler responses checked now. Platforms may retain previously cached cards.'}
