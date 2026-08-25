"""What "Check installation" counts as installed.

A customer can be installed in four different ways, and only one of them puts
a <script> tag on the page. The scan has to recognise all of them, and still
say no to a site that simply has not installed anything.
"""
from backend.api.v1.routes_install import _scan_html


NPM_PACKAGE_HEAD = """<!doctype html><html><head>
<!-- MyMetaView --><meta property="og:title" content="Pricing that scales">
<meta property="og:image" content="https://cdn.mymetaview.com/card.png"><!-- /MyMetaView -->
<title>Pricing</title></head><body>hi</body></html>"""

WORDPRESS_HEAD = """<html><head>
<!-- MyMetaView Previews -->
<meta property="og:title" content="Pricing that scales" />
<!-- /MyMetaView Previews -->
</head></html>"""


def test_snippet_tag_is_recognised():
    html = '<html><head><script src="https://mymetaview.com/snippet.js" defer></script></head></html>'
    assert _scan_html(html)["snippet_found"] is True


def test_server_rendered_tags_count_as_installed():
    """The npm package and the Worker serve crawlers without loading the snippet."""
    scan = _scan_html(NPM_PACKAGE_HEAD)
    assert scan["snippet_found"] is True
    assert scan["og_title"] == "Pricing that scales"
    assert scan["og_image"] == "https://cdn.mymetaview.com/card.png"


def test_wordpress_marker_counts_as_installed():
    assert _scan_html(WORDPRESS_HEAD)["snippet_found"] is True


def test_a_page_with_its_own_tags_is_not_an_install():
    html = (
        '<html><head><meta property="og:title" content="Their own title">'
        '<script src="https://other-vendor.com/snippet.js"></script></head></html>'
    )
    scan = _scan_html(html)
    assert scan["snippet_found"] is False
    assert scan["og_title"] == "Their own title"
