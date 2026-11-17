"""Corpus scoring must work with local storage and no HTTP asset server."""
from io import BytesIO
from unittest.mock import patch
from PIL import Image
from backend.services.r2_client import settings, store_file_locally
from backend.services.preview.corpus.scoring import load_card_image, score_run
from backend.scripts.preview_engine.run_corpus import _save_card, _read_local_card
from backend.services.preview.net.session import FetchResult


def test_local_card_is_preserved_and_scored_without_network(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MEDIA_ROOT', str(tmp_path / 'media'))
    monkeypatch.setattr(settings, 'ASSET_BASE_URL', 'http://localhost:8000')
    data = BytesIO()
    Image.new('RGB', (1200, 630), 'white').save(data, format='PNG')
    png = data.getvalue()
    image_url = store_file_locally(png, 'previews/card.png')
    records = [{'url': 'https://example.test/page', 'status': 'ok', 'primary_image_url': image_url}]
    run_dir = tmp_path / 'run'
    with patch('backend.services.preview.net.fetch', side_effect=AssertionError('Local cards must not use HTTP')):
        assert load_card_image(image_url) == png
        saved = _save_card(image_url, run_dir, records[0]['url'])
        assert saved.read_bytes() == png
        assert _read_local_card(run_dir, records, image_url) == png
        # The recovery path must work even when the run's archived copy is gone.
        saved.unlink()
        assert _read_local_card(run_dir, records, image_url) == png
        scores = score_run(records)
        assert scores.scored_count == 1
        assert scores.render_failure_count == 0
        # Loading succeeds; an intentionally blank card must still fail quality.
        assert scores.pass_rate == 0


def test_remote_cards_still_use_guarded_fetch():
    url = 'https://cdn.example.test/card.png'
    with patch('backend.services.preview.net.fetch', return_value=FetchResult(url, True, 200, b'png', 'image/png')) as fetch:
        assert load_card_image(url) == b'png'
        fetch.assert_called_once_with(url, timeout=15.0)


def test_missing_card_remains_a_scoring_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, 'MEDIA_ROOT', str(tmp_path))
    monkeypatch.setattr(settings, 'ASSET_BASE_URL', 'http://localhost:8000')
    url = 'http://localhost:8000/static/media/missing.png'
    with patch('backend.services.preview.net.fetch', return_value=FetchResult(url, False, 404)):
        result = score_run([{'url': 'https://example.test', 'status': 'ok', 'primary_image_url': url}])
    assert result.scored_count == 0
    assert result.render_failure_count == 1
