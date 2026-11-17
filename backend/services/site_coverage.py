"""Change detection ignores navigation; page identity preserves case and meaningful queries."""
import hashlib
import json
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from backend.services.preview.extraction.page_facts import extract_page_facts

TRACKING = {'fbclid','gclid','msclkid','mc_cid','mc_eid','mmv_variant'}

def page_identity(url):
    p=urlsplit(url)
    query=[(k,v) for k,v in parse_qsl(p.query,keep_blank_values=True) if not k.lower().startswith('utm_') and k.lower() not in TRACKING]
    return urlunsplit((p.scheme.lower(),p.netloc.lower(),p.path.rstrip('/') or '/',urlencode(query),''))

def page_observation(html, url, domain):
    facts=extract_page_facts(html,url)
    candidate=page_identity(facts['canonical_url'])
    if (urlsplit(candidate).hostname or '').removeprefix('www.') != domain.lower().removeprefix('www.'):
        candidate=page_identity(url)
    content={key:facts.get(key) for key in ('title','description','fields','visible_text','language')}
    fingerprint=hashlib.sha256(json.dumps(content,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return candidate,fingerprint
