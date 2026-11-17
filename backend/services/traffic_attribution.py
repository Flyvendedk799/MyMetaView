from urllib.parse import urlsplit,parse_qs
from backend.utils.crawler_detection import detect_crawler

SOCIAL_HOSTS=('facebook.com','instagram.com','linkedin.com','twitter.com','x.com','t.co','reddit.com',
              'pinterest.com','slack.com','discord.com','threads.net','bsky.app','youtube.com','t.me')

def social_visit_attribution(url,referrer,user_agent):
    if detect_crawler(user_agent)[0]:return None
    referrer = referrer or ''
    if referrer and '://' not in referrer:
        referrer = 'https://' + referrer
    host=(urlsplit(referrer).hostname or '').lower()
    if not any(host==domain or host.endswith('.'+domain) for domain in SOCIAL_HOSTS):return None
    query=parse_qs(urlsplit(url).query)
    variant=(query.get('mmv_variant') or [None])[0]
    return {'event_source':'social_referral','campaign':(query.get('utm_campaign') or [''])[0][:120] or None,
            'variant':variant if variant in ('a','b','c','main') else None}
