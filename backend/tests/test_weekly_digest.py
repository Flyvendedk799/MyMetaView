"""Automated tests for the weekly performance digest system.

Covers acceptance criteria C1-C8:
- Digest metrics calculation (impressions, clicks, CTR, WoW deltas and percentage changes, top previews).
- Skipping zero-activity accounts (0 impressions across both 7-day windows).
- Opt-out handling (weekly_digest_enabled toggle in Account Settings and unsubscribe link).
- Unsubscribe token validation (valid, expired, tampered, invalid).
- Duplicate-send suppression (subsequent runs in the same ISO week send nothing).
- Trigger endpoint authentication (CRON_SECRET / WEEKLY_DIGEST_SECRET) and dry_run.
- Non-aborting batch error handling when an individual delivery fails.
"""
import base64
from datetime import date, datetime, timedelta
from threading import Thread
from unittest.mock import patch

from sqlalchemy.orm import sessionmaker

from backend.models.domain import Domain
from backend.models.organization import Organization
from backend.models.organization_member import OrganizationMember, OrganizationRole
from backend.models.user import User
from backend.models.preview import Preview
from backend.models.analytics_aggregate import AnalyticsDailyAggregate
from backend.models.weekly_digest_send import WeeklyDigestSend
from backend.services.digest_token_service import (
    generate_digest_unsubscribe_token,
    verify_digest_unsubscribe_token,
)
from backend.services.email_service import build_weekly_digest_email, send_weekly_digest_email
from backend.services.weekly_digest_service import (
    calculate_domain_digest_metrics,
    process_weekly_digest,
)
from backend.tests.test_platform_flows import _session, _signup, client  # noqa: F401


class TestDigestTokenService:
    def test_token_validity(self):
        email = "founder@example.com"
        token = generate_digest_unsubscribe_token(email)
        is_valid, extracted_email, reason = verify_digest_unsubscribe_token(token)
        assert is_valid is True
        assert extracted_email == email
        assert reason == "valid"

    def test_token_expiration(self):
        email = "expired@example.com"
        past_ts = int((datetime.utcnow() - timedelta(days=31)).timestamp())
        token = generate_digest_unsubscribe_token(email, timestamp=past_ts)
        is_valid, extracted_email, reason = verify_digest_unsubscribe_token(token, max_age_seconds=30 * 86400)
        assert is_valid is False
        assert extracted_email == email
        assert reason == "expired"

    def test_token_tampered_signature(self):
        email = "victim@example.com"
        token = generate_digest_unsubscribe_token(email)
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        # Corrupt the signature
        tampered_raw = f"{parts[0]}|{parts[1]}|bad_signature"
        tampered = base64.urlsafe_b64encode(tampered_raw.encode("utf-8")).decode("utf-8")
        is_valid, extracted_email, reason = verify_digest_unsubscribe_token(tampered)
        assert is_valid is False
        assert reason == "tampered"

    def test_token_tampered_payload(self):
        email = "victim@example.com"
        token = generate_digest_unsubscribe_token(email)
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        # Corrupt the email part
        tampered_raw = f"attacker@example.com|{parts[1]}|{parts[2]}"
        tampered = base64.urlsafe_b64encode(tampered_raw.encode("utf-8")).decode("utf-8")
        is_valid, extracted_email, reason = verify_digest_unsubscribe_token(tampered)
        assert is_valid is False
        assert reason == "tampered"

    def test_token_malformed(self):
        is_valid, extracted_email, reason = verify_digest_unsubscribe_token("not-a-token")
        assert is_valid is False
        assert reason == "invalid"


class TestUnsubscribeRoute:
    def test_digest_token_unsubscribes_user(self, client):
        token_auth, org_id = _signup(client, "unsub_me@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "unsub_me@example.com").one()
        assert user.weekly_digest_enabled is True
        db.close()

        unsub_token = generate_digest_unsubscribe_token("unsub_me@example.com")
        r = client.get(f"/api/v1/newsletter/unsubscribe?token={unsub_token}")
        assert r.status_code == 200, r.text
        assert r.json()["success"] is True

        db = _session()
        user = db.query(User).filter(User.email == "unsub_me@example.com").one()
        assert user.weekly_digest_enabled is False
        db.close()

    def test_expired_digest_token_returns_400(self, client):
        past_ts = int((datetime.utcnow() - timedelta(days=35)).timestamp())
        expired_token = generate_digest_unsubscribe_token("someone@example.com", timestamp=past_ts)
        r = client.get(f"/api/v1/newsletter/unsubscribe?token={expired_token}")
        assert r.status_code == 400
        assert "expired" in r.json()["detail"].lower()

    def test_tampered_digest_token_returns_400(self, client):
        token = generate_digest_unsubscribe_token("someone@example.com")
        raw = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = raw.split("|")
        tampered_raw = f"{parts[0]}|{parts[1]}|bad_sig"
        tampered = base64.urlsafe_b64encode(tampered_raw.encode("utf-8")).decode("utf-8")
        r = client.get(f"/api/v1/newsletter/unsubscribe?token={tampered}")
        assert r.status_code == 400
        assert "tampered" in r.json()["detail"].lower()


class TestAccountPreferences:
    def test_get_and_update_preferences(self, client):
        token, org_id = _signup(client, "prefs_user@example.com")
        auth_header = {"Authorization": f"Bearer {token}"}

        # Check default is True
        r = client.get("/api/v1/account/preferences", headers=auth_header)
        assert r.status_code == 200, r.text
        assert r.json()["weekly_digest_enabled"] is True
        assert r.json()["weekly_performance_email"] is True

        # Toggle to False
        r = client.patch(
            "/api/v1/account/preferences",
            json={"weekly_performance_email": False},
            headers=auth_header,
        )
        assert r.status_code == 200, r.text
        assert r.json()["weekly_digest_enabled"] is False
        assert r.json()["weekly_performance_email"] is False

        # Verify via GET
        r = client.get("/api/v1/account/preferences", headers=auth_header)
        assert r.status_code == 200
        assert r.json()["weekly_digest_enabled"] is False

        # Toggle back to True via weekly_digest_enabled field
        r = client.patch(
            "/api/v1/account/preferences",
            json={"weekly_digest_enabled": True},
            headers=auth_header,
        )
        assert r.status_code == 200
        assert r.json()["weekly_digest_enabled"] is True


class TestDigestMetricsCalculation:
    def test_metrics_and_wow_comparison(self, client):
        _signup(client, "metrics_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "metrics_user@example.com").one()
        domain = Domain(name="analytics.test", user_id=user.id, status="verified")
        db.add(domain)
        db.commit()
        db.refresh(domain)

        preview1 = Preview(
            url="https://analytics.test/page1",
            domain="analytics.test",
            title="Page 1",
            type="article",
            image_url="https://analytics.test/image1.png",
            user_id=user.id,
        )
        preview2 = Preview(
            url="https://analytics.test/page2",
            domain="analytics.test",
            title="Page 2",
            type="article",
            image_url="https://analytics.test/image2.png",
            user_id=user.id,
        )
        db.add_all([preview1, preview2])
        db.commit()

        as_of = date(2026, 11, 2)  # Monday
        # Current window: Oct 26 to Nov 1 (7 days)
        # Previous window: Oct 19 to Oct 25 (7 days)
        start_curr = as_of - timedelta(days=7)  # 2026-10-26
        end_curr = as_of - timedelta(days=1)    # 2026-11-01
        start_prev = as_of - timedelta(days=14) # 2026-10-19
        end_prev = as_of - timedelta(days=8)   # 2026-10-25

        # Seed previous window: 1000 impressions, 50 clicks (5% CTR)
        agg_prev = AnalyticsDailyAggregate(
            domain_id=domain.id,
            user_id=user.id,
            date=start_prev,
            impressions=1000,
            clicks=50,
        )
        # Seed current window: 1500 impressions, 120 clicks (8% CTR)
        # Split between preview1 and preview2
        agg_curr1 = AnalyticsDailyAggregate(
            domain_id=domain.id,
            user_id=user.id,
            preview_id=preview1.id,
            date=start_curr,
            impressions=1000,
            clicks=90,
        )
        agg_curr2 = AnalyticsDailyAggregate(
            domain_id=domain.id,
            user_id=user.id,
            preview_id=preview2.id,
            date=start_curr + timedelta(days=1),
            impressions=500,
            clicks=30,
        )
        db.add_all([agg_prev, agg_curr1, agg_curr2])
        db.commit()

        metrics = calculate_domain_digest_metrics(
            db=db,
            domain=domain,
            start_current=start_curr,
            end_current=end_curr,
            start_previous=start_prev,
            end_previous=end_prev,
        )
        db.close()

        assert metrics["domain_name"] == "analytics.test"
        assert metrics["impressions"] == 1500
        assert metrics["impressions_prev"] == 1000
        assert metrics["impressions_delta"] == 500
        assert metrics["impressions_change_pct"] == 50.0

        assert metrics["clicks"] == 120
        assert metrics["clicks_prev"] == 50
        assert metrics["clicks_delta"] == 70
        assert metrics["clicks_change_pct"] == 140.0

        assert metrics["ctr"] == 8.0
        assert metrics["ctr_prev"] == 5.0
        assert metrics["ctr_delta"] == 3.0

        # Top previews check
        assert len(metrics["top_previews"]) == 2
        assert metrics["top_previews"][0]["title"] == "Page 1"
        assert metrics["top_previews"][0]["clicks"] == 90
        assert metrics["top_previews"][1]["title"] == "Page 2"
        assert metrics["top_previews"][1]["clicks"] == 30


class TestWeeklyDigestProcess:
    def test_zero_activity_accounts_are_skipped(self, client):
        _signup(client, "inactive_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "inactive_user@example.com").one()
        dom = Domain(name="empty.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()

        res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=True)
        db.close()

        skipped_users = [s for s in res["skipped"] if s["email"] == "inactive_user@example.com"]
        assert len(skipped_users) == 1
        assert skipped_users[0]["reason"] == "zero_impressions"

    def test_unverified_domains_are_skipped(self, client):
        _signup(client, "unverified_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "unverified_user@example.com").one()
        dom = Domain(name="pending.test", user_id=user.id, status="pending")
        db.add(dom)
        db.commit()

        res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=True)
        db.close()

        skipped_users = [s for s in res["skipped"] if s["email"] == "unverified_user@example.com"]
        assert len(skipped_users) == 1
        assert skipped_users[0]["reason"] == "no_verified_domains"

    def test_opted_out_accounts_are_skipped(self, client):
        _signup(client, "optedout_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "optedout_user@example.com").one()
        user.weekly_digest_enabled = False
        dom = Domain(name="active.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()

        agg = AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=500,
            clicks=25,
        )
        db.add(agg)
        db.commit()

        res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=True)
        db.close()

        skipped_users = [s for s in res["skipped"] if s["email"] == "optedout_user@example.com"]
        assert len(skipped_users) == 1
        assert skipped_users[0]["reason"] == "opted_out"

    def test_duplicate_send_guard(self, client):
        _signup(client, "duplicate_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "duplicate_user@example.com").one()
        dom = Domain(name="active2.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()

        agg = AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=300,
            clicks=15,
        )
        db.add(agg)
        db.commit()

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email") as mock_send:
            # First run: should send and record send
            res1 = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)
            assert any(s["email"] == "duplicate_user@example.com" for s in res1["sent"])
            assert mock_send.call_count == 1

            # Verify send recorded in weekly_digest_sends
            iso_year, iso_week, _ = date(2026, 11, 2).isocalendar()
            send_record = db.query(WeeklyDigestSend).filter(
                WeeklyDigestSend.user_id == user.id,
                WeeklyDigestSend.year == iso_year,
                WeeklyDigestSend.iso_week == iso_week,
            ).first()
            assert send_record is not None

            # Second run in same week: should be skipped
            mock_send.reset_mock()
            res2 = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)
            skipped_dup = [s for s in res2["skipped"] if s["email"] == "duplicate_user@example.com"]
            assert len(skipped_dup) == 1
            assert skipped_dup[0]["reason"] == "already_sent_this_week"
            assert mock_send.call_count == 0

        db.close()

    def test_non_aborting_send_failure(self, client):
        _signup(client, "fail1@example.com")
        _signup(client, "succeed2@example.com")
        db = _session()
        u1 = db.query(User).filter(User.email == "fail1@example.com").one()
        u2 = db.query(User).filter(User.email == "succeed2@example.com").one()

        d1 = Domain(name="d1.test", user_id=u1.id, status="verified")
        d2 = Domain(name="d2.test", user_id=u2.id, status="verified")
        db.add_all([d1, d2])
        db.commit()

        db.add_all([
            AnalyticsDailyAggregate(domain_id=d1.id, user_id=u1.id, date=date(2026, 10, 30), impressions=100, clicks=5),
            AnalyticsDailyAggregate(domain_id=d2.id, user_id=u2.id, date=date(2026, 10, 30), impressions=200, clicks=10),
        ])
        db.commit()

        def side_effect_send(to_email, **kwargs):
            if to_email == "fail1@example.com":
                raise RuntimeError("SMTP connection dropped")
            return True

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", side_effect=side_effect_send):
            res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)

        assert any(f["email"] == "fail1@example.com" for f in res["failed"])
        assert any(s["email"] == "succeed2@example.com" for s in res["sent"])
        db.close()

    def test_send_returns_false_is_treated_as_failure_and_does_not_record_send(self, client):
        _signup(client, "send_fails@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "send_fails@example.com").one()
        dom = Domain(name="faildelivery.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()

        agg = AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=200,
            clicks=10,
        )
        db.add(agg)
        db.commit()

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", return_value=False) as mock_send:
            res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)

        assert mock_send.call_count == 1
        assert any(f["email"] == "send_fails@example.com" for f in res["failed"])
        assert not any(s["email"] == "send_fails@example.com" for s in res["sent"])

        iso_year, iso_week, _ = date(2026, 11, 2).isocalendar()
        send_record = db.query(WeeklyDigestSend).filter(
            WeeklyDigestSend.user_id == user.id,
            WeeklyDigestSend.year == iso_year,
            WeeklyDigestSend.iso_week == iso_week,
        ).first()
        assert send_record is None
        db.close()

    def test_failed_delivery_can_be_retried(self, client):
        _signup(client, "retry_send@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "retry_send@example.com").one()
        dom = Domain(name="retry.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()
        db.add(AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=80,
            clicks=4,
        ))
        db.commit()

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", return_value=False):
            first = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)
        assert any(f["email"] == "retry_send@example.com" for f in first["failed"])

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", return_value=True) as mock_send:
            second = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)
        assert mock_send.call_count == 1
        assert any(s["email"] == "retry_send@example.com" for s in second["sent"])
        db.close()

    def test_claim_exists_before_delivery(self, client):
        _signup(client, "claim_first@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "claim_first@example.com").one()
        dom = Domain(name="claim.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()
        db.add(AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=40,
            clicks=2,
        ))
        db.commit()
        seen = {}

        def send(to_email, **kwargs):
            iso_year, iso_week, _ = date(2026, 11, 2).isocalendar()
            row = db.query(WeeklyDigestSend).filter(
                WeeklyDigestSend.user_id == user.id,
                WeeklyDigestSend.year == iso_year,
                WeeklyDigestSend.iso_week == iso_week,
            ).one()
            seen["email"] = row.recipient_email
            assert to_email == "claim_first@example.com"
            return True

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", side_effect=send):
            res = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=False)

        assert seen["email"] == "claim_first@example.com"
        assert any(s["email"] == "claim_first@example.com" for s in res["sent"])
        db.close()

    def test_overlapping_runs_deliver_once(self, client):
        _signup(client, "race_user@example.com")
        db = _session()
        user = db.query(User).filter(User.email == "race_user@example.com").one()
        dom = Domain(name="race.test", user_id=user.id, status="verified")
        db.add(dom)
        db.commit()
        db.add(AnalyticsDailyAggregate(
            domain_id=dom.id,
            user_id=user.id,
            date=date(2026, 10, 30),
            impressions=90,
            clicks=9,
        ))
        db.commit()
        engine = db.get_bind()
        db.close()

        session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
        calls = []
        results = []
        errors = []

        def send(to_email, **kwargs):
            if to_email == "race_user@example.com":
                calls.append(to_email)
                import time
                time.sleep(0.3)
            return True

        def run():
            session = session_factory()
            try:
                results.append(process_weekly_digest(session, as_of_date=date(2026, 11, 2), dry_run=False))
            except Exception as exc:  # noqa: BLE001 — the assertion below reports it
                errors.append(exc)
            finally:
                session.close()

        with patch("backend.services.weekly_digest_service.send_weekly_digest_email", side_effect=send):
            threads = [Thread(target=run), Thread(target=run)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=15)

        assert errors == []
        assert calls.count("race_user@example.com") == 1
        sent = [
            item
            for res in results
            for item in res["sent"]
            if item["email"] == "race_user@example.com"
        ]
        assert len(sent) == 1

    def test_org_domain_follows_current_access_not_creator(self, client):
        _signup(client, "editor_left@example.com")
        _signup(client, "org_owner@example.com")
        db = _session()
        editor = db.query(User).filter(User.email == "editor_left@example.com").one()
        owner = db.query(User).filter(User.email == "org_owner@example.com").one()
        org = db.query(Organization).filter(Organization.owner_user_id == owner.id).one()
        db.add(OrganizationMember(
            organization_id=org.id,
            user_id=editor.id,
            role=OrganizationRole.EDITOR,
        ))
        org_domain = Domain(
            name="shared.test",
            user_id=editor.id,
            organization_id=org.id,
            status="verified",
        )
        personal = Domain(name="editor-personal.test", user_id=editor.id, status="verified")
        db.add_all([org_domain, personal])
        db.commit()
        db.add_all([
            AnalyticsDailyAggregate(
                domain_id=org_domain.id, user_id=editor.id, date=date(2026, 10, 30), impressions=100, clicks=5,
            ),
            AnalyticsDailyAggregate(
                domain_id=personal.id, user_id=editor.id, date=date(2026, 10, 30), impressions=50, clicks=2,
            ),
        ])
        db.commit()

        while_member = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=True)
        editor_mail = next(item for item in while_member["would_send"] if item["email"] == "editor_left@example.com")
        owner_mail = next(item for item in while_member["would_send"] if item["email"] == "org_owner@example.com")
        assert {d["domain_name"] for d in editor_mail["domains"]} == {"shared.test", "editor-personal.test"}
        assert {d["domain_name"] for d in owner_mail["domains"]} == {"shared.test"}

        membership = db.query(OrganizationMember).filter(
            OrganizationMember.organization_id == org.id,
            OrganizationMember.user_id == editor.id,
            OrganizationMember.role == OrganizationRole.EDITOR,
        ).one()
        db.delete(membership)
        db.commit()

        after_removal = process_weekly_digest(db, as_of_date=date(2026, 11, 2), dry_run=True)
        editor_mail = next(item for item in after_removal["would_send"] if item["email"] == "editor_left@example.com")
        owner_mail = next(item for item in after_removal["would_send"] if item["email"] == "org_owner@example.com")
        assert {d["domain_name"] for d in editor_mail["domains"]} == {"editor-personal.test"}
        assert {d["domain_name"] for d in owner_mail["domains"]} == {"shared.test"}
        db.close()


class TestEmailTemplateAndContent:
    def test_email_builder_has_metaview_branding_and_links(self):
        domain_summary = [{
            "domain_name": "example.com & co",
            "impressions": 1250,
            "impressions_prev": 1000,
            "impressions_delta": 250,
            "impressions_change_pct": 25.0,
            "clicks": 100,
            "clicks_prev": 80,
            "clicks_delta": 20,
            "clicks_change_pct": 25.0,
            "ctr": 8.0,
            "ctr_prev": 8.0,
            "ctr_delta": 0.0,
            "top_previews": [
                {"title": "Pricing <Pro> & More", "url": "https://example.com/pricing?a=1&b=2", "clicks": 60, "impressions": 500},
                {"title": "Blog post", "url": "https://example.com/blog", "clicks": 40, "impressions": 400},
            ],
        }]

        unsub_url = "https://mymetaview.com/unsubscribe?token=sample"
        analytics_url = "https://mymetaview.com/app/analytics"

        subject, html, text = build_weekly_digest_email(
            user_email="reader@example.com",
            domain_summaries=domain_summary,
            unsubscribe_url=unsub_url,
            analytics_url=analytics_url,
        )

        assert "Weekly Performance Digest" in subject
        # Sender name and branding
        assert "MetaView" in html
        assert "1,250" in html
        assert "+250 (+25.0%) vs prev week" in html
        assert unsub_url in html
        assert analytics_url in html

        # HTML escaping assertions for domain_name, preview title, and url
        assert "example.com &amp; co" in html
        assert "Pricing &lt;Pro&gt; &amp; More" in html
        assert "https://example.com/pricing?a=1&amp;b=2" in html

        # Plain-text checks (verify HTML escaping is HTML-only)
        assert "example.com & co" in text
        assert "Pricing <Pro> & More" in text
        assert "&amp;" not in text
        assert "&lt;" not in text
        assert "1,250" in text
        assert unsub_url in text
        assert analytics_url in text

    def test_send_weekly_digest_email_sender_is_metaview(self):
        with patch("backend.services.email_service.send_email") as mock_send:
            send_weekly_digest_email(
                to_email="test@example.com",
                domain_summaries=[],
                unsubscribe_url="https://mymetaview.com/unsubscribe",
                analytics_url="https://mymetaview.com/app/analytics",
            )
            assert mock_send.called
            call_kwargs = mock_send.call_args[1]
            assert call_kwargs["from_name"] == "MetaView"


class TestTriggerEndpoint:
    def test_unauthorized_without_secret_set_in_env(self, client, monkeypatch):
        monkeypatch.delenv("CRON_SECRET", raising=False)
        monkeypatch.delenv("WEEKLY_DIGEST_SECRET", raising=False)
        r = client.post("/api/v1/jobs/weekly-digest", headers={"X-Cron-Secret": "any-secret"})
        assert r.status_code == 401

    def test_unauthorized_without_secret_header(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123")
        r = client.post("/api/v1/jobs/weekly-digest")
        assert r.status_code == 401

    def test_unauthorized_with_wrong_secret(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123")
        r = client.post("/api/v1/jobs/weekly-digest", headers={"X-Cron-Secret": "wrong-secret"})
        assert r.status_code == 401

    def test_authorized_with_cron_secret_header(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123")
        r = client.post(
            "/api/v1/jobs/weekly-digest?dry_run=true",
            headers={"X-Cron-Secret": "test-cron-secret-123"},
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["dry_run"] is True
        assert "period" in data

    def test_authorized_with_bearer_token(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123")
        r = client.post(
            "/api/v1/jobs/weekly-digest?dry_run=true",
            headers={"Authorization": "Bearer test-cron-secret-123"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["dry_run"] is True

    def test_live_run_is_queued(self, client, monkeypatch):
        monkeypatch.setenv("CRON_SECRET", "test-cron-secret-123")
        with patch("backend.api.v1.routes_jobs.get_rq_redis_connection", return_value=object()), \
             patch("backend.api.v1.routes_jobs.Queue") as mock_queue:
            mock_queue.return_value.enqueue.return_value.id = "digest-job-1"
            r = client.post(
                "/api/v1/jobs/weekly-digest",
                headers={"X-Cron-Secret": "test-cron-secret-123"},
            )
        assert r.status_code == 202, r.text
        body = r.json()
        assert body["queued"] is True
        assert body["job_id"] == "digest-job-1"
        assert body["dry_run"] is False
        assert mock_queue.call_args.args[0] == "bulk_generation"
        enqueued = mock_queue.return_value.enqueue.call_args
        assert enqueued.args[0].__name__ == "run_weekly_digest"
        assert enqueued.kwargs["job_timeout"] == "60m"
