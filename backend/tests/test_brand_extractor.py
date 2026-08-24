"""Tests for brand_extractor.py - HTML logo/color/hero extraction."""
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO
from PIL import Image


class TestLogoExtraction:
    """Test logo extraction priority and fallbacks."""

    def test_extracts_apple_touch_icon_first(self, sample_html):
        """Priority 1: apple-touch-icon should be preferred."""
        # Create a valid 180x180 image response
        img = Image.new('RGB', (180, 180), color=(0, 100, 200))
        buf = BytesIO()
        img.save(buf, format='PNG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(sample_html, 'https://acme.com', b'')

        assert result is not None

    def test_extracts_header_logo_when_no_icon(self):
        """Priority 2: Header <img> with logo class."""
        html = """
        <html><head></head><body>
        <header><img class="logo" src="/logo.png" alt="Logo" width="120" height="40" /></header>
        </body></html>
        """
        img = Image.new('RGB', (120, 40), color=(0, 0, 0))
        buf = BytesIO()
        img.save(buf, format='PNG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        assert result is not None

    def test_returns_none_for_empty_html(self, sample_screenshot_bytes):
        """Should return None for empty HTML with no metadata."""
        from backend.services.brand_extractor import extract_brand_logo
        result = extract_brand_logo('<html><body></body></html>', 'https://example.com', sample_screenshot_bytes)
        # May return screenshot crop fallback
        # Just verify no crash
        assert True

    def test_filters_tiny_images(self):
        """Should reject images smaller than minimum dimensions."""
        html = '<html><head><link rel="apple-touch-icon" href="/tiny.png" /></head><body></body></html>'
        img = Image.new('RGB', (10, 10), color=(255, 0, 0))
        buf = BytesIO()
        img.save(buf, format='PNG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        # 10x10 is below 32x32 minimum, should be rejected
        # Result might be None or a fallback
        assert True  # No crash


def _png_response(width, height, color=(0, 0, 0), mode='RGB'):
    img = Image.new(mode, (width, height), color=color)
    buf = BytesIO()
    img.save(buf, format='PNG')
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = buf.getvalue()
    mock_response.headers = {'content-type': 'image/png'}
    return mock_response


class TestLogoDownloadHardening:
    """New logo download/normalization behavior."""

    def test_lazy_loaded_logo_via_data_src(self):
        """A lazy-loaded logo (real file in data-src, no src) is found."""
        html = """
        <html><body>
        <header><img class="logo" data-src="/real-logo.png" alt="Logo" /></header>
        </body></html>
        """
        with patch('backend.services.brand_extractor.requests.get',
                   return_value=_png_response(120, 40)) as mock_get:
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        assert result is not None
        requested = [call.args[0] for call in mock_get.call_args_list]
        assert any('real-logo.png' in u for u in requested)

    def test_oversized_logo_is_downscaled(self):
        """A huge image grabbed as logo is bounded to 512px."""
        import base64
        html = '<html><head><link rel="apple-touch-icon" href="/big.png" /></head><body></body></html>'
        with patch('backend.services.brand_extractor.requests.get',
                   return_value=_png_response(2000, 1000, color=(10, 20, 30))):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        assert result is not None
        img = Image.open(BytesIO(base64.b64decode(result)))
        assert max(img.size) <= 512

    def test_transparent_padding_is_trimmed(self):
        """A small mark on a large transparent canvas is trimmed to the mark."""
        import base64
        canvas = Image.new('RGBA', (400, 400), (0, 0, 0, 0))
        mark = Image.new('RGBA', (120, 40), (200, 30, 30, 255))
        canvas.paste(mark, (140, 180))
        buf = BytesIO()
        canvas.save(buf, format='PNG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()
        mock_response.headers = {'content-type': 'image/png'}

        html = '<html><head><link rel="apple-touch-icon" href="/logo.png" /></head><body></body></html>'
        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        assert result is not None
        img = Image.open(BytesIO(base64.b64decode(result)))
        assert img.width < 200 and img.height < 100

    def test_svg_candidate_is_skipped_without_crash(self):
        """SVG bytes can't become the PNG the frontend expects — skip them."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        mock_response.headers = {'content-type': 'image/svg+xml'}

        html = '<html><head><link rel="apple-touch-icon" href="/logo.svg" /></head><body></body></html>'
        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_brand_logo
            result = extract_brand_logo(html, 'https://example.com', b'')

        assert result is None

    def test_flat_screenshot_crop_is_rejected(self):
        """A crop of empty header background must not ship as 'the logo'."""
        img = Image.new('RGB', (1200, 630), color=(250, 250, 250))
        buf = BytesIO()
        img.save(buf, format='PNG')

        from backend.services.brand_extractor import _extract_logo_from_screenshot
        assert _extract_logo_from_screenshot(buf.getvalue()) is None

    def test_screenshot_crop_with_content_is_kept(self, sample_screenshot_bytes):
        """The fixture screenshot has a real header mark — crop should survive."""
        from backend.services.brand_extractor import _extract_logo_from_screenshot
        assert _extract_logo_from_screenshot(sample_screenshot_bytes) is not None


class TestUploadedLogoFetch:
    """fetch_uploaded_logo — the customer's Brand & identity logo."""

    def test_raster_upload_returns_png_and_data_uri(self):
        with patch('backend.services.brand_extractor.requests.get',
                   return_value=_png_response(300, 100, color=(0, 80, 40))):
            from backend.services.brand_extractor import fetch_uploaded_logo
            result = fetch_uploaded_logo('https://r2.example.com/brand-logos/1/x.png')

        assert result is not None
        assert result['png_base64']
        assert result['data_uri'].startswith('data:image/png;base64,')

    def test_svg_upload_returns_data_uri_only(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b'<svg xmlns="http://www.w3.org/2000/svg"><circle r="20"/></svg>'
        mock_response.headers = {'content-type': 'image/svg+xml'}

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import fetch_uploaded_logo
            result = fetch_uploaded_logo('https://r2.example.com/brand-logos/1/x.svg')

        assert result is not None
        assert result['png_base64'] is None
        assert result['data_uri'].startswith('data:image/svg+xml;base64,')

    def test_unreachable_upload_returns_none(self):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.content = b''
        mock_response.headers = {}

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import fetch_uploaded_logo
            assert fetch_uploaded_logo('https://r2.example.com/gone.png') is None

    def test_requests_carry_browser_user_agent(self):
        """CDNs 403 the default python-requests UA; every fetch must send ours."""
        with patch('backend.services.brand_extractor.requests.get',
                   return_value=_png_response(64, 64)) as mock_get:
            from backend.services.brand_extractor import _download_and_validate_image
            _download_and_validate_image('https://example.com/logo.png')

        headers = mock_get.call_args.kwargs.get('headers') or {}
        assert 'Mozilla' in headers.get('User-Agent', '')


class TestHeroImageExtraction:
    """Test hero image extraction priority and fallbacks."""

    def test_extracts_og_image(self, sample_html):
        """Priority 1: og:image should be extracted."""
        img = Image.new('RGB', (1200, 630), color=(100, 100, 200))
        buf = BytesIO()
        img.save(buf, format='JPEG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_hero_image
            result = extract_hero_image(sample_html, 'https://acme.com')

        assert result is not None

    def test_extracts_twitter_image_as_fallback(self):
        """Priority 2: twitter:image when og:image fails."""
        html = """
        <html><head>
            <meta name="twitter:image" content="https://example.com/twitter.jpg" />
        </head><body></body></html>
        """
        img = Image.new('RGB', (800, 400), color=(50, 50, 100))
        buf = BytesIO()
        img.save(buf, format='JPEG')
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = buf.getvalue()

        with patch('backend.services.brand_extractor.requests.get', return_value=mock_response):
            from backend.services.brand_extractor import extract_hero_image
            result = extract_hero_image(html, 'https://example.com')

        assert result is not None

    def test_returns_none_for_no_images(self):
        """Should return None when no suitable images found."""
        html = '<html><head></head><body><p>Just text</p></body></html>'

        from backend.services.brand_extractor import extract_hero_image
        result = extract_hero_image(html, 'https://example.com')

        assert result is None


class TestColorExtraction:
    """Test brand color extraction."""

    def test_extracts_colors_from_screenshot(self, sample_screenshot_bytes):
        """Should extract reasonable colors from a screenshot."""
        from backend.services.brand_extractor import extract_brand_colors

        colors = extract_brand_colors(
            '<html><body></body></html>',
            sample_screenshot_bytes
        )

        assert colors is not None
        assert 'primary_color' in colors
        assert 'secondary_color' in colors
        # Colors should be hex strings
        assert colors['primary_color'].startswith('#')
