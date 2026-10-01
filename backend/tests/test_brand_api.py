"""The My Site tab's API, end to end against a real (SQLite) database.

Pins the connection between what a customer saves and what the engine reads:
saving works on every plan, a domain follows the account default until it is
customised, writes are validated, the sample renders the unsaved draft through
the engine's own rules, and "Fill from my site" reads the real page.
"""
from __future__ import annotations

import base64
import io
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from backend.models.brand import BrandSettings as BrandRow
from backend.models.domain import Domain
from backend.tests.test_platform_flows import _session, _set_plan, _signup, client  # noqa: F401


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _domain(org_id, name="acme.test"):
    db = _session()
    row = Domain(name=name, organization_id=org_id, status="verified")
    db.add(row)
    db.commit()
    domain_id = row.id
    db.close()
    return domain_id


def _rows(org_id):
    db = _session()
    rows = [(r.domain_id, r.brand_name) for r in db.query(BrandRow).filter(BrandRow.organization_id == org_id)]
    db.close()
    return rows


def _form(body, **changes):
    """What the tab sends: every field, as it was loaded, plus the edits."""
    keys = (
        "primary_color", "secondary_color", "accent_color", "font_family", "logo_url",
        "brand_name", "tagline", "brand_description", "audience", "voice",
        "preview_layout", "preview_panel", "preview_accent", "force_brand_colors",
        "hide_watermark", "white_label_name",
    )
    return {**{k: body.get(k) for k in keys}, **changes}


class TestSaving:
    def test_a_plan_without_white_label_can_save(self, client):
        """The tab always sends white_label_name (null). That used to 402 every
        save on every plan except Agency."""
        token, org_id = _signup(client, "starter@example.com")
        _set_plan(org_id, "active", "starter")
        body = client.get("/api/v1/brand", headers=_auth(token)).json()

        r = client.put("/api/v1/brand", json=_form(body, brand_name="Acme"), headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["brand_name"] == "Acme"

    def test_setting_a_white_label_name_still_needs_the_plan(self, client):
        token, org_id = _signup(client, "growth@example.com")
        _set_plan(org_id, "active", "growth")
        r = client.put("/api/v1/brand", json={"white_label_name": "Ours"}, headers=_auth(token))
        assert r.status_code == 402

    def test_the_white_label_name_survives_a_cached_read(self, client):
        """The cached view was hand-built and left the field out, so the next
        save sent null and wiped it."""
        token, org_id = _signup(client, "agency@example.com")
        _set_plan(org_id, "active", "agency")
        r = client.put("/api/v1/brand", json={"white_label_name": "Ours"}, headers=_auth(token))
        assert r.status_code == 200, r.text
        cache = {}
        with patch("backend.api.v1.routes_brand.get_cached_brand_settings",
                   side_effect=lambda org, dom=None: cache.get((org, dom))), \
                patch("backend.api.v1.routes_brand.set_cached_brand_settings",
                      side_effect=lambda org, value, dom=None: cache.__setitem__((org, dom), value)):
            first = client.get("/api/v1/brand", headers=_auth(token)).json()
            second = client.get("/api/v1/brand", headers=_auth(token)).json()
        assert first["white_label_name"] == second["white_label_name"] == "Ours"


class TestValidation:
    @pytest.fixture()
    def token(self, client):
        token, org_id = _signup(client, "valid@example.com")
        _set_plan(org_id, "active", "growth")
        return token

    def test_colours_are_normalised(self, client, token):
        r = client.put("/api/v1/brand", json={"primary_color": "#ABC"}, headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["primary_color"] == "#aabbcc"

    @pytest.mark.parametrize("payload", [
        {"primary_color": "blue"},
        {"preview_layout": "carousel"},
        {"voice": "sarcastic"},
        {"font_family": "Comic Sans"},
        {"logo_url": "file:///etc/passwd"},
        {"brand_name": "x" * 81},
    ])
    def test_values_the_card_cannot_use_are_refused(self, client, token, payload):
        r = client.put("/api/v1/brand", json=payload, headers=_auth(token))
        assert r.status_code == 422, r.text

    def test_the_stock_inter_reads_as_auto(self, client, token):
        r = client.put("/api/v1/brand", json={"font_family": "Inter"}, headers=_auth(token))
        assert r.json()["font_family"] == "auto"

    def test_blank_text_means_unset_and_null_cannot_clear_a_colour(self, client, token):
        client.put("/api/v1/brand", json={"brand_name": "Acme", "primary_color": "#112233"},
                   headers=_auth(token))
        r = client.put("/api/v1/brand", json={"brand_name": "   ", "primary_color": None},
                       headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["brand_name"] is None
        assert r.json()["primary_color"] == "#112233"


class TestInheritance:
    def test_reading_a_domain_writes_nothing_and_follows_the_default(self, client):
        token, org_id = _signup(client, "inherit@example.com")
        domain_id = _domain(org_id)
        client.put("/api/v1/brand", json={"brand_name": "Account"}, headers=_auth(token))

        body = client.get(f"/api/v1/brand?domain_id={domain_id}", headers=_auth(token)).json()
        assert body["inherits_default"] is True
        assert body["brand_name"] == "Account"
        assert _rows(org_id) == [(None, "Account")]

        # Editing the default later still reaches the domain that follows it.
        client.put("/api/v1/brand", json={"brand_name": "Renamed"}, headers=_auth(token))
        body = client.get(f"/api/v1/brand?domain_id={domain_id}", headers=_auth(token)).json()
        assert body["brand_name"] == "Renamed"

    def test_saving_a_domain_gives_it_its_own_brand_and_reset_returns_it(self, client):
        token, org_id = _signup(client, "own@example.com")
        domain_id = _domain(org_id)
        client.put("/api/v1/brand", json={"brand_name": "Account", "tagline": "Default line"},
                   headers=_auth(token))

        r = client.put(f"/api/v1/brand?domain_id={domain_id}", json={"brand_name": "Site"},
                       headers=_auth(token))
        assert r.json()["inherits_default"] is False
        assert r.json()["tagline"] == "Default line"  # seeded from the default

        r = client.delete(f"/api/v1/brand?domain_id={domain_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["inherits_default"] is True
        assert r.json()["brand_name"] == "Account"
        assert (domain_id, "Site") not in _rows(org_id)

    def test_another_orgs_domain_is_not_reachable(self, client):
        token, _ = _signup(client, "a@example.com")
        _, other_org = _signup(client, "b@example.com")
        foreign = _domain(other_org, "other.test")
        assert client.get(f"/api/v1/brand?domain_id={foreign}", headers=_auth(token)).status_code == 404
        assert client.delete(f"/api/v1/brand?domain_id={foreign}", headers=_auth(token)).status_code == 404


class TestSample:
    def _render(self, client, token, draft=None, domain_id=None):
        captured = {}

        def fake_render(**kwargs):
            captured.update(kwargs)
            return b"\x89PNG fake"

        query = f"?domain_id={domain_id}" if domain_id else ""
        with patch("backend.services.premium_card_renderer.render_premium_card", side_effect=fake_render):
            r = client.post(f"/api/v1/brand/preview{query}", json=draft, headers=_auth(token))
        assert r.status_code == 200, r.text
        return r.json(), captured

    def test_it_draws_the_unsaved_draft(self, client):
        token, org_id = _signup(client, "draft@example.com")
        _set_plan(org_id, "active", "growth")
        body, card = self._render(client, token, {
            "tagline": "Draft line", "primary_color": "#C2410C", "preview_panel": "dark",
            "font_family": "IBM Plex Sans",
        })
        assert body["image_data_uri"].startswith("data:image/png;base64,")
        assert card["subtitle"] == "Draft line"
        assert card["colors"]["primary_color"] == "#c2410c"
        assert card["composition"]["panel_color_role"] == "dark"
        assert card["font_family"] == "IBM Plex Sans"
        # Nothing was saved by previewing.
        assert client.get("/api/v1/brand", headers=_auth(token)).json()["tagline"] is None

    def test_it_follows_the_plan_and_the_font_rule(self, client):
        token, org_id = _signup(client, "gated@example.com")
        _set_plan(org_id, "active", "starter")
        _, card = self._render(client, token, {"preview_panel": "dark", "hide_watermark": True})
        assert card["composition"]["panel_color_role"] == "primary"
        assert card["hide_watermark"] is False
        assert card["font_family"] is None  # stock → the card's own type

    def test_it_prints_the_real_hostname(self, client):
        token, org_id = _signup(client, "host@example.com")
        domain_id = _domain(org_id, "shop.acme.test")
        _, card = self._render(client, token, domain_id=domain_id)
        assert card["url"].startswith("shop.acme.test/")

    def test_an_invalid_draft_is_refused(self, client):
        token, _ = _signup(client, "bad@example.com")
        r = client.post("/api/v1/brand/preview", json={"primary_color": "nope"}, headers=_auth(token))
        assert r.status_code == 422


def _png_data_uri(color=(200, 40, 40, 255), size=(120, 48)):
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", size, (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([4, 4, size[0] - 30, size[1] - 4], fill=color)
    ImageDraw.Draw(img).ellipse([size[0] - 26, 8, size[0] - 4, size[1] - 8], fill=(20, 20, 20, 255))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


class TestSampleSpec:
    def test_the_logo_gets_the_engines_contrast_treatment(self):
        """A dark mark on a dark panel is moved or plated, as on a real card."""
        from backend.services.preview.brand_sample import sample_spec

        dark_logo = _png_data_uri(color=(10, 12, 14, 255))
        spec = sample_spec(
            {"primary_color": "#0b0f14", "preview_panel": "dark"},
            host="acme.test", logo_data_uri=dark_logo,
        )
        moved = spec["composition"]["panel_color_role"] != "dark"
        plated = bool(spec["composition"].get("logo_plate"))
        assert moved or plated or spec["logo_data_uri"] is None


HOME = """<!doctype html><html><head>
<title>Acme Analytics — Product analytics without the setup</title>
<meta property="og:site_name" content="Acme Analytics">
<meta name="description" content="Acme shows SaaS teams which features drive retention, without a data engineer.">
</head><body><h1>Welcome</h1></body></html>"""


class TestDetect:
    def _detect(self, html=HOME, cached=None):
        from backend.services.preview.extraction import site_brand

        page = SimpleNamespace(ok=bool(html), text=html or "", status=200 if html else 0, error="down")
        with patch("backend.services.preview.net.fetch", return_value=page), \
                patch.object(site_brand.BrandCache, "get", return_value=cached), \
                patch.object(site_brand, "_logo", return_value=None):
            return site_brand.detect_site_brand("acme.test", organization_id=1, upload_logo=False)

    def test_it_reads_the_identity_off_the_home_page(self):
        found = self._detect()
        assert found["brand_name"] == "Acme Analytics"
        assert found["tagline"] == "Product analytics without the setup"
        assert found["brand_description"].startswith("Acme shows SaaS teams")

    def test_a_palette_sampled_by_an_earlier_generation_wins(self):
        found = self._detect(cached={
            "brand_name": "Acme", "palette_source": "sampled",
            "colors": {"primary_color": "#C2410C", "accent_color": "#FACC15"},
        })
        assert found["primary_color"] == "#c2410c"
        assert found["palette_source"] == "sampled"

    def test_the_synthetic_slate_is_never_suggested(self):
        found = self._detect(cached={
            "palette_source": "derived", "colors": {"primary_color": "#475569"},
        }, html=HOME)
        assert found.get("primary_color") != "#475569"

    def test_an_unreachable_site_says_so(self):
        from backend.services.preview.extraction.site_brand import SiteUnreachable

        with pytest.raises(SiteUnreachable):
            self._detect(html=None)

    def test_the_route_needs_an_owned_domain(self, client):
        token, org_id = _signup(client, "detect@example.com")
        domain_id = _domain(org_id)
        with patch("backend.services.preview.extraction.site_brand.detect_site_brand",
                   return_value={"source_url": "https://acme.test/", "brand_name": "Acme"}):
            r = client.post(f"/api/v1/brand/detect?domain_id={domain_id}", headers=_auth(token))
        assert r.status_code == 200, r.text
        assert r.json()["brand_name"] == "Acme"
        assert client.post("/api/v1/brand/detect?domain_id=999", headers=_auth(token)).status_code == 404


class TestStoredLogos:
    def test_our_own_stored_asset_is_read_from_disk(self, tmp_path):
        """Self-hosted without R2: the logo URL points at our own media route,
        which the SSRF guard (rightly) refuses to fetch over HTTP."""
        from backend.core.config import settings
        from backend.services.r2_client import read_stored_asset

        target = tmp_path / "brand-logos" / "1"
        target.mkdir(parents=True)
        (target / "logo.png").write_bytes(b"png-bytes")
        with patch.object(settings, "MEDIA_ROOT", str(tmp_path)), \
                patch.object(settings, "ASSET_BASE_URL", "http://localhost:8000"):
            assert read_stored_asset("http://localhost:8000/static/media/brand-logos/1/logo.png") == b"png-bytes"
            assert read_stored_asset("http://localhost:8000/static/media/../secrets.txt") is None
            assert read_stored_asset("https://elsewhere.test/static/media/brand-logos/1/logo.png") is None


class TestStockValues:
    def test_an_untouched_account_reads_as_no_preference(self):
        from backend.services import brand_resolver
        from backend.services.preview.branding import chosen_font, customised_palette, engine_payload

        payload = engine_payload(
            brand_resolver.stock_row(1), can_card_controls=True, can_hide_watermark=True,
        )
        assert chosen_font(payload) is None
        assert customised_palette(payload) == {}
        assert chosen_font({"font_family": "Inter"}) is None
        assert chosen_font({"font_family": "IBM Plex Sans"}) == "IBM Plex Sans"
