from io import BytesIO
from unittest.mock import patch
from PIL import Image
from backend.services.preview.net.session import FetchResult
from backend.services.share_delivery import check_crawler


def test_snippet_alone_is_not_ready():
    page=FetchResult('https://site.test', True, 200, b'<head><script src="snippet.js"></script></head>')
    with patch('backend.services.share_delivery.fetch', return_value=page):
        result=check_crawler(page.url, 'Card', 'https://cdn.test/card.png', 'Facebook', 'bot')
    assert not result['ready']
    assert len(result['issues']) == 2


def test_valid_bytes_and_matching_head_pass():
    url='https://cdn.test/card.png'
    page=FetchResult('https://site.test',True,200,f'<head><meta property="og:title" content="Card"><meta property="og:image" content="{url}"></head>'.encode())
    buf=BytesIO(); Image.new('RGB',(1200,630)).save(buf,format='PNG')
    image=FetchResult(url,True,200,buf.getvalue(),'image/png')
    with patch('backend.services.share_delivery.fetch', side_effect=[page,image]):
        assert check_crawler(page.url,'Card',url,'Facebook','bot')['ready']


def test_conflicting_tags_fail_even_if_first_is_correct():
    page=FetchResult('https://site.test', True,200,b'<head><meta property="og:title" content="Card"><meta property="og:title" content="Old"></head>')
    with patch('backend.services.share_delivery.fetch',return_value=page):
        result=check_crawler(page.url,'Card','image','X','bot')
    assert any('Conflicting' in s for s in result['issues'])
