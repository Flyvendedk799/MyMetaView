"""API-level tests for the auth flows and the public serving path.

Runs the real FastAPI app against a temporary SQLite database. Covers the
endpoints added for platform completeness: password reset, change-password,
the social-visit beacon, and the honesty guarantees of /public/preview
(no fabricated copy, impressions recorded for crawler fetches).
"""
import os
import tempfile

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.db.session import get_db
from backend.main import app


@pytest.fixture()
def client():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    engine = create_engine(
        f"sqlite:///{path}", connect_args={"check_same_thread": False}
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
        os.unlink(path)


def _signup_and_login(client, email="user@example.com", password="testpass123"):
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/auth/login", data={"username": email, "password": password}
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


class TestAuthFlows:
    def test_signup_login_me(self, client):
        token = _signup_and_login(client)
        r = client.get("/api/v1/auth/me", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["email"] == "user@example.com"
        # Signup grants a trialing org, surfaced on the user.
        assert body["subscription_status"] == "trialing"

    def test_forgot_password_never_reveals_accounts(self, client):
        r = client.post(
            "/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}
        )
        assert r.status_code == 202
        # Same answer whether or not the account exists.
        _signup_and_login(client)
        r2 = client.post(
            "/api/v1/auth/forgot-password", json={"email": "user@example.com"}
        )
        assert r2.status_code == 202
        assert r.json()["message"] == r2.json()["message"]

    def test_reset_password_round_trip(self, client):
        _signup_and_login(client)

        # Build a valid token the same way the email link does.
        from backend.api.v1.routes_auth import _reset_token_for
        from backend.models.user import User

        override = app.dependency_overrides[get_db]
        db = next(override())
        user = db.query(User).filter(User.email == "user@example.com").first()
        token = _reset_token_for(user)

        r = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "brandnewpass1"},
        )
        assert r.status_code == 200, r.text

        # Old password dead, new one works.
        r = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "testpass123"},
        )
        assert r.status_code == 401
        r = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "brandnewpass1"},
        )
        assert r.status_code == 200

        # The token died with the password change (single-use in effect).
        r = client.post(
            "/api/v1/auth/reset-password",
            json={"token": token, "new_password": "anotherpass1"},
        )
        assert r.status_code == 400

    def test_reset_password_rejects_garbage_token(self, client):
        r = client.post(
            "/api/v1/auth/reset-password",
            json={"token": "not-a-token", "new_password": "whatever123"},
        )
        assert r.status_code == 400

    def test_change_password_requires_current(self, client):
        token = _signup_and_login(client)
        r = client.post(
            "/api/v1/account/change-password",
            json={"current_password": "wrong", "new_password": "newpassword1"},
            headers=_auth(token),
        )
        assert r.status_code == 400
        r = client.post(
            "/api/v1/account/change-password",
            json={"current_password": "testpass123", "new_password": "newpassword1"},
            headers=_auth(token),
        )
        assert r.status_code == 200
        r = client.post(
            "/api/v1/auth/login",
            data={"username": "user@example.com", "password": "newpassword1"},
        )
        assert r.status_code == 200


class TestPublicServing:
    def _connect_verified_domain(self, client, token, name="acme.test"):
        r = client.post(
            "/api/v1/domains", json={"name": name}, headers=_auth(token)
        )
        assert r.status_code in (200, 201), r.text
        domain_id = r.json()["id"]
        # Simulate a passed verification check (DNS can't resolve in tests).
        from backend.models.domain import Domain

        override = app.dependency_overrides[get_db]
        db = next(override())
        row = db.query(Domain).filter(Domain.id == domain_id).first()
        row.status = "verified"
        db.commit()
        return domain_id

    def test_fallback_never_fabricates_copy(self, client):
        r = client.get(
            "/api/v1/public/preview",
            params={"full_url": "https://unknown-domain.test/page"},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "fallback"
        # The old behavior shipped sentences like "Preview not configured
        # yet." as the og:description. Empty means integrations keep the
        # page's own tags.
        assert body["description"] == ""
        assert "via.placeholder.com" not in (body["image_url"] or "")

    def test_crawler_fetch_records_impression(self, client):
        token = _signup_and_login(client)
        self._connect_verified_domain(client, token)

        r = client.get(
            "/api/v1/public/preview",
            params={"full_url": "https://acme.test/pricing"},
            headers={"User-Agent": "facebookexternalhit/1.1"},
        )
        assert r.status_code == 200

        from backend.models.analytics_event import AnalyticsEvent

        override = app.dependency_overrides[get_db]
        db = next(override())
        events = db.query(AnalyticsEvent).filter(
            AnalyticsEvent.event_type == "impression"
        ).all()
        assert len(events) == 1
        assert events[0].domain_id is not None

    def test_social_visit_records_click(self, client):
        token = _signup_and_login(client)
        self._connect_verified_domain(client, token)

        r = client.post(
            "/api/v1/track/social-visit",
            params={"url": "https://acme.test/pricing", "ref": "facebook.com"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        from backend.models.analytics_event import AnalyticsEvent

        override = app.dependency_overrides[get_db]
        db = next(override())
        clicks = db.query(AnalyticsEvent).filter(
            AnalyticsEvent.event_type == "click"
        ).all()
        assert len(clicks) == 1
        assert clicks[0].referrer == "facebook.com"

    def test_social_visit_ignores_unknown_domain(self, client):
        r = client.post(
            "/api/v1/track/social-visit",
            params={"url": "https://not-ours.test/", "ref": "facebook.com"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "ignored"
