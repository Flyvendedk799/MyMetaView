"""Product-flow gates added while finishing the platform.

Invites persist as hashes, account deletion transfers or retires the org,
plans without variants or advanced analytics are rejected, platform cards
render from a stored spec, and the legacy generate route stays retired.
"""
import os
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db import Base
from backend.db.session import get_db
from backend.main import app
from backend.models.organization import Organization
from backend.models.organization_invite import OrganizationInvite
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.models.preview import Preview
from backend.models.user import User


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


def _session():
    override = app.dependency_overrides[get_db]
    return next(override())


def _signup(client, email, password="testpass123"):
    r = client.post("/api/v1/auth/signup", json={"email": email, "password": password})
    assert r.status_code == 201, r.text
    r = client.post("/api/v1/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    orgs = client.get("/api/v1/organizations", headers={"Authorization": f"Bearer {token}"})
    assert orgs.status_code == 200, orgs.text
    return token, orgs.json()[0]["id"]


def _set_plan(org_id, status, plan):
    db = _session()
    org = db.query(Organization).filter(Organization.id == org_id).first()
    org.subscription_status = status
    org.subscription_plan = plan
    db.commit()
    db.close()


class TestLegacyGenerate:
    def test_generate_is_gone(self, client):
        token, _org = _signup(client, "gone@example.com")
        r = client.post(
            "/api/v1/previews/generate",
            json={"url": "https://example.com", "domain": "example.com"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 410
        assert "jobs/preview" in r.json()["detail"]


class TestInvites:
    def test_invite_is_stored_as_a_hash(self, client):
        token, org_id = _signup(client, "owner@example.com")
        r = client.post(
            f"/api/v1/organizations/{org_id}/invite",
            json={"role": "viewer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200, r.text
        raw = r.json()["invite_token"]
        db = _session()
        row = db.query(OrganizationInvite).filter(OrganizationInvite.organization_id == org_id).one()
        assert row.token_hash != raw
        assert len(row.token_hash) == 64
        db.close()


class TestAccountDeletion:
    def test_transfers_to_longest_tenured_admin(self, client):
        owner_token, org_id = _signup(client, "owner@example.com")
        admin_token, _ = _signup(client, "admin@example.com")
        db = _session()
        admin = db.query(User).filter(User.email == "admin@example.com").one()
        db.add(OrganizationMember(
            organization_id=org_id,
            user_id=admin.id,
            role=OrganizationRole.ADMIN,
        ))
        db.commit()
        admin_id = admin.id
        db.close()

        r = client.delete("/api/v1/account", headers={"Authorization": f"Bearer {owner_token}"})
        assert r.status_code == 200, r.text
        outcome = r.json()["organizations"][0]
        assert outcome["action"] == "transferred"
        assert outcome["new_owner_user_id"] == admin_id

        org = client.get(
            f"/api/v1/organizations/{org_id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert org.status_code == 200
        assert org.json()["owner_user_id"] == admin_id

    def test_sole_member_soft_deletes_the_org(self, client):
        token, org_id = _signup(client, "solo@example.com")
        r = client.delete("/api/v1/account", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200, r.text
        assert r.json()["organizations"][0]["action"] == "deleted"
        db = _session()
        org = db.query(Organization).filter(Organization.id == org_id).one()
        assert org.deleted_at is not None
        db.close()


class TestPlanGates:
    def test_variants_rejected_without_the_feature(self, client):
        token, org_id = _signup(client, "starter@example.com")
        _set_plan(org_id, "active", "starter")
        r = client.put(
            "/api/v1/preview-variants/1",
            json={"title": "B"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 402

    def test_advanced_analytics_rejected_on_free(self, client):
        token, org_id = _signup(client, "free@example.com")
        _set_plan(org_id, "canceled", "growth")
        r = client.get(
            "/api/v1/analytics/domains",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 402
        overview = client.get(
            "/api/v1/analytics/overview",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert overview.status_code == 200


class TestPlatformCards:
    def test_renders_from_the_stored_spec(self, client):
        token, org_id = _signup(client, "cards@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "cards@example.com").one()
        preview = Preview(
            url="https://example.com/post",
            domain="example.com",
            title="A card",
            type="article",
            image_url="https://cdn.example/wide.png",
            organization_id=org_id,
            user_id=user.id,
            render_spec={"composition": {"layout": "typographic"}},
        )
        db.add(preview)
        db.commit()
        preview_id = preview.id
        db.close()

        with patch(
            "backend.api.v1.routes_previews.render_platform_sizes",
            return_value={"wide": "https://cdn.example/wide.png", "square": "https://cdn.example/sq.png"},
        ):
            r = client.post(
                f"/api/v1/previews/{preview_id}/platform-cards",
                headers={"Authorization": f"Bearer {token}"},
            )
        assert r.status_code == 200, r.text
        sizes = {card["size"] for card in r.json()["cards"]}
        assert sizes == {"wide", "square"}
