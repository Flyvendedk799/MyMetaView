from unittest.mock import MagicMock, patch
import pytest
from redis.exceptions import ConnectionError
from backend.services import generation_lock as module


def test_duplicate_generation_is_rejected_without_releasing_owner():
    client = MagicMock()
    client.lock.return_value.acquire.return_value = False
    with patch('backend.services.preview_cache.get_redis_client', return_value=client):
        with pytest.raises(RuntimeError, match='already generating'):
            with module.generation_lock(1, 'https://example.test/page'):
                pytest.fail('A duplicate generation must not start')
    client.lock.return_value.release.assert_not_called()


def test_generation_releases_lease_after_failure():
    client = MagicMock()
    with patch('backend.services.preview_cache.get_redis_client', return_value=client):
        with pytest.raises(ValueError):
            with module.generation_lock(1, 'https://example.test/page'):
                raise ValueError('Render failed')
    client.lock.return_value.release.assert_called_once()


@pytest.mark.parametrize('environment', ['development', 'production'])
def test_redis_failure_only_allows_local_development(environment):
    client = MagicMock()
    client.lock.return_value.acquire.side_effect = ConnectionError('Offline')
    with patch('backend.services.preview_cache.get_redis_client', return_value=client), patch.object(module, 'ENV', environment):
        if environment == 'production':
            with pytest.raises(RuntimeError, match='coordination is unavailable'):
                with module.generation_lock(1, 'https://example.test/page'):
                    pytest.fail('Production must preserve exclusive generation')
        else:
            with module.generation_lock(1, 'https://example.test/page'):
                pass
    client.lock.return_value.release.assert_not_called()
