from types import SimpleNamespace
from unittest.mock import patch
import pytest
from fastapi import HTTPException
from backend.services.card_revision import render_revision, apply_revision


def card():
    return SimpleNamespace(url='https://example.com', title='Old', description='Old copy',
        render_spec={'composition': {'layout': 'split'}}, platform_images={'square': 'old'},
        variants=[SimpleNamespace(variant_key='a'), SimpleNamespace(variant_key='b',
            title='Alternative', subtitle='Proof', description='Proof')])


def test_failed_size_preserves_every_field():
    preview = card()
    with patch('backend.services.card_revision.rerender_card', side_effect=[('new', 'split'), (None, None)]):
        with pytest.raises(HTTPException):
            render_revision(preview, preview.render_spec, 'New', 'New copy')
    assert preview.title == 'Old'
    assert preview.platform_images == {'square': 'old'}


def test_bundle_updates_sizes_spec_and_variants_together():
    preview = card()
    with patch('backend.services.card_revision.rerender_card', side_effect=[('wide', 'split'), ('square', 'split'), ('b', 'split')]):
        rendered = render_revision(preview, preview.render_spec, 'New', 'New copy')
    assert preview.title == 'Old'
    apply_revision(preview, rendered)
    assert preview.title == preview.render_spec['title'] == 'New'
    assert preview.platform_images == {'wide': 'wide', 'square': 'square'}
    assert preview.variants[0].title == 'New'
    assert preview.variants[1].image_url == 'b'
