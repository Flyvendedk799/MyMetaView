"""Snippet install routes.

Everything the dashboard needs to get the embed snippet onto a customer's site
and prove that it worked:

* the exact tag to paste, plus per-platform variants
* a server-side check that the tag is really on the page
* a heartbeat the snippet itself reports, which covers sites a fetch cannot reach
* generated, ready-to-use install artifacts (WordPress plugin, GTM container,
  Cloudflare Worker) so most platforms are a single download away
"""
from __future__ import annotations

import io
import ipaddress
import json
import logging
import re
import socket
import zipfile
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import urlparse

import requests
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.deps import get_current_org, get_current_user
from backend.db.session import get_db
from backend.models.domain import Domain as DomainModel
from backend.models.organization import Organization
from backend.models.user import User
from backend.services.activity_logger import get_client_ip
from backend.services.rate_limiter import check_rate_limit, get_rate_limit_key_for_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/install", tags=["install"])
public_router = APIRouter(prefix="/api/v1/public/install", tags=["install"])

SNIPPET_VERSION = "2.0.0"
SNIPPET_PATH = "/snippet.js"

# A domain counts as "live" while its snippet has checked in recently.
HEARTBEAT_FRESH_FOR = timedelta(days=7)

# Bound the verification fetch: this is a user-triggered request to a third-party
# host, so it must never hold a worker open.
VERIFY_TIMEOUT_SECONDS = 8
VERIFY_MAX_BYTES = 512 * 1024

VERIFY_USER_AGENT = (
    f"MyMetaViewInstallCheck/{SNIPPET_VERSION} "
    "(+https://mymetaview.com/docs/install)"
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InstallDomainStatus(BaseModel):
    """Install state for a single connected domain."""

    id: int
    name: str
    status: str
    verified: bool
    snippet_installed_at: Optional[datetime] = None
    snippet_last_seen_at: Optional[datetime] = None
    snippet_version: Optional[str] = None
    snippet_live: bool = Field(False, description="True if the snippet checked in recently")
    snippet_outdated: bool = Field(False, description="True if a newer snippet version is available")


class InstallConfig(BaseModel):
    """Everything the install page needs to render."""

    snippet_url: str
    snippet_tag: str
    snippet_version: str
    api_origin: str
    domains: List[InstallDomainStatus]


class VerifyInstallRequest(BaseModel):
    domain_id: Optional[int] = Field(None, description="Connected domain to check")
    url: Optional[str] = Field(None, description="Specific page to check, defaults to the domain root")


class VerifyInstallResponse(BaseModel):
    ok: bool
    checked_url: str
    snippet_found: bool
    snippet_version: Optional[str] = None
    heartbeat_seen: bool = False
    heartbeat_at: Optional[datetime] = None
    og_title: Optional[str] = None
    og_image: Optional[str] = None
    has_own_og_tags: bool = False
    status: str = Field(..., description="installed | not_found | unreachable | blocked")
    message: str
    hint: Optional[str] = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _public_origin() -> str:
    """Origin the snippet is served from."""
    return settings.PUBLIC_BASE_URL.rstrip("/")


def _snippet_url() -> str:
    return f"{_public_origin()}{SNIPPET_PATH}"


def _snippet_tag(domain_name: Optional[str] = None) -> str:
    """The tag a customer pastes. data-site is only added when it earns its place."""
    attrs = f'src="{_snippet_url()}" defer'
    if domain_name:
        attrs += f' data-site="{domain_name}"'
    return f"<script {attrs}></script>"


def _normalize_host(value: str) -> str:
    """Reduce a hostname or URL to a bare lowercase host."""
    if not value:
        return ""
    candidate = value.strip().lower()
    if "//" in candidate:
        candidate = urlparse(candidate).netloc or candidate
    candidate = candidate.split("/")[0].split("@")[-1].split(":")[0].rstrip(".")
    if candidate.startswith("www."):
        candidate = candidate[4:]
    return candidate


def _is_publicly_routable(hostname: str) -> bool:
    """Reject hosts that resolve to private space, so verify cannot be used as an SSRF probe."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    for info in infos:
        address = info[4][0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return bool(infos)


def _heartbeat_is_fresh(domain: DomainModel) -> bool:
    if not domain.snippet_last_seen_at:
        return False
    return (datetime.utcnow() - domain.snippet_last_seen_at) <= HEARTBEAT_FRESH_FOR


def _to_status(domain: DomainModel) -> InstallDomainStatus:
    return InstallDomainStatus(
        id=domain.id,
        name=domain.name,
        status=domain.status,
        verified=domain.status == "verified",
        snippet_installed_at=domain.snippet_installed_at,
        snippet_last_seen_at=domain.snippet_last_seen_at,
        snippet_version=domain.snippet_version,
        snippet_live=_heartbeat_is_fresh(domain),
        snippet_outdated=bool(domain.snippet_version) and domain.snippet_version != SNIPPET_VERSION,
    )


def _get_org_domain(db: Session, org: Organization, domain_id: int) -> DomainModel:
    domain = (
        db.query(DomainModel)
        .filter(DomainModel.id == domain_id, DomainModel.organization_id == org.id)
        .first()
    )
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return domain


def _resolve_target_domain(
    db: Session, org: Organization, domain_id: Optional[int], domain_name: Optional[str]
) -> DomainModel:
    """Pick the domain an install artifact is generated for."""
    if domain_id is not None:
        return _get_org_domain(db, org, domain_id)

    query = db.query(DomainModel).filter(DomainModel.organization_id == org.id)
    if domain_name:
        domain = query.filter(DomainModel.name == _normalize_host(domain_name)).first()
        if not domain:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
        return domain

    domain = query.order_by(DomainModel.created_at.asc()).first()
    if not domain:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Connect a domain before generating install files.",
        )
    return domain


# ---------------------------------------------------------------------------
# Config + status
# ---------------------------------------------------------------------------


@router.get("/config", response_model=InstallConfig)
def get_install_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Snippet details plus the install state of every connected domain."""
    domains = (
        db.query(DomainModel)
        .filter(DomainModel.organization_id == current_org.id)
        .order_by(DomainModel.created_at.asc())
        .all()
    )

    return InstallConfig(
        snippet_url=_snippet_url(),
        snippet_tag=_snippet_tag(),
        snippet_version=SNIPPET_VERSION,
        api_origin=_public_origin(),
        domains=[_to_status(domain) for domain in domains],
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

_SCRIPT_SRC_RE = re.compile(
    r"""<script[^>]+src\s*=\s*["']([^"']+)["']""", re.IGNORECASE
)
_META_TAG_RE = re.compile(r"<meta\b[^>]*>", re.IGNORECASE)
_META_KEY_RE = re.compile(
    r"""(?:property|name)\s*=\s*["'](og:title|og:image)["']""", re.IGNORECASE
)
_CONTENT_RE = re.compile(r"""content\s*=\s*["']([^"']*)["']""", re.IGNORECASE)


def _looks_like_our_snippet(src: str) -> bool:
    """Recognise our tag without matching some other vendor's snippet.js."""
    parsed = urlparse(src if "//" in src else f"//{src}")
    our_host = urlparse(_public_origin()).hostname or ""
    host = (parsed.hostname or "").lower()
    path = parsed.path.lower()

    if host and our_host and host == our_host.lower():
        return True
    # Relative or proxied path, e.g. a customer serving the file from their CDN.
    return (path.endswith("/snippet.js") or path.endswith("/s.js")) and "mymetaview" in src.lower()


def _scan_html(html: str) -> dict:
    found = any(_looks_like_our_snippet(src) for src in _SCRIPT_SRC_RE.findall(html))

    # A bundler or tag template can inline the snippet instead of linking it.
    if not found:
        our_host = (urlparse(_public_origin()).hostname or "").lower()
        found = bool(our_host) and our_host in html.lower()

    og = {}
    for tag in _META_TAG_RE.findall(html):
        key_match = _META_KEY_RE.search(tag)
        if not key_match:
            continue
        content_match = _CONTENT_RE.search(tag)
        if content_match and content_match.group(1).strip():
            og.setdefault(key_match.group(1).lower(), content_match.group(1).strip())

    return {
        "snippet_found": found,
        "og_title": og.get("og:title"),
        "og_image": og.get("og:image"),
    }


@router.post("/verify", response_model=VerifyInstallResponse)
def verify_install(
    payload: VerifyInstallRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """Fetch a page and report whether the snippet is on it.

    A negative fetch result is not conclusive — plenty of sites inject the tag
    client-side, or sit behind a bot wall. When that happens we fall back to the
    snippet's own heartbeat, which is authoritative.
    """
    client_ip = get_client_ip(request)
    if not check_rate_limit(get_rate_limit_key_for_ip(client_ip, "install_verify"), limit=30, window_seconds=300):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please wait a moment and try again.",
        )

    domain: Optional[DomainModel] = None
    if payload.domain_id is not None:
        domain = _get_org_domain(db, current_org, payload.domain_id)

    if payload.url:
        target = payload.url.strip()
        if not target.startswith(("http://", "https://")):
            target = f"https://{target}"
    elif domain:
        target = f"https://{domain.name}"
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide a domain_id or a url to check.",
        )

    parsed = urlparse(target)
    hostname = parsed.hostname or ""
    if not hostname:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid URL.")

    # Only ever fetch a host the caller's organization has connected.
    owned_hosts = {
        d.name
        for d in db.query(DomainModel).filter(DomainModel.organization_id == current_org.id).all()
    }
    if _normalize_host(hostname) not in owned_hosts:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only verify domains connected to your organization.",
        )

    if domain is None:
        domain = (
            db.query(DomainModel)
            .filter(
                DomainModel.organization_id == current_org.id,
                DomainModel.name == _normalize_host(hostname),
            )
            .first()
        )

    heartbeat_seen = bool(domain and _heartbeat_is_fresh(domain))
    heartbeat_at = domain.snippet_last_seen_at if domain else None

    if not _is_publicly_routable(hostname):
        return VerifyInstallResponse(
            ok=heartbeat_seen,
            checked_url=target,
            snippet_found=False,
            heartbeat_seen=heartbeat_seen,
            heartbeat_at=heartbeat_at,
            status="installed" if heartbeat_seen else "blocked",
            message=(
                f"We could not reach {hostname} from here, but the snippet has been reporting in from this domain."
                if heartbeat_seen
                else f"{hostname} could not be resolved to a public address."
            ),
            hint=None
            if heartbeat_seen
            else "Check the domain spelling, or load a page on the site once so the snippet can report in.",
        )

    try:
        response = requests.get(
            target,
            timeout=VERIFY_TIMEOUT_SECONDS,
            headers={"User-Agent": VERIFY_USER_AGENT, "Accept": "text/html,*/*"},
            allow_redirects=True,
            stream=True,
        )
        final_host = urlparse(response.url).hostname or ""
        if final_host and not _is_publicly_routable(final_host):
            raise requests.RequestException("redirected to a non-public address")

        chunks: List[bytes] = []
        total = 0
        for chunk in response.iter_content(8192):
            chunks.append(chunk)
            total += len(chunk)
            if total >= VERIFY_MAX_BYTES:
                break
        response.close()
        html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
        http_status = response.status_code
    except requests.RequestException as exc:
        logger.info("Install verification could not reach %s: %s", target, exc)
        return VerifyInstallResponse(
            ok=heartbeat_seen,
            checked_url=target,
            snippet_found=False,
            heartbeat_seen=heartbeat_seen,
            heartbeat_at=heartbeat_at,
            status="installed" if heartbeat_seen else "unreachable",
            message=(
                "We could not load the page, but the snippet has been reporting in from this domain."
                if heartbeat_seen
                else "We could not load that page to check it."
            ),
            hint=None
            if heartbeat_seen
            else "The site may be private, behind a bot wall, or temporarily down. Loading any page on the site once also confirms the install.",
        )

    if http_status >= 400:
        return VerifyInstallResponse(
            ok=heartbeat_seen,
            checked_url=target,
            snippet_found=False,
            heartbeat_seen=heartbeat_seen,
            heartbeat_at=heartbeat_at,
            status="installed" if heartbeat_seen else "unreachable",
            message=(
                f"The page returned HTTP {http_status}, but the snippet has been reporting in from this domain."
                if heartbeat_seen
                else f"The page returned HTTP {http_status}."
            ),
            hint=None if heartbeat_seen else "Try checking a specific page URL that is publicly reachable.",
        )

    scan = _scan_html(html)
    snippet_found = scan["snippet_found"]
    installed = snippet_found or heartbeat_seen

    if snippet_found:
        message = "The snippet is installed and serving on this page."
    elif heartbeat_seen:
        message = "The snippet is running on this domain, but we could not see the tag in the page source."
    else:
        message = "We loaded the page but did not find the snippet."

    hint = None
    if not snippet_found and heartbeat_seen:
        hint = "That is normal when a tag manager or a framework injects the tag after load."
    elif not installed:
        hint = "Paste the tag into your site's <head>, publish, then check again."

    return VerifyInstallResponse(
        ok=installed,
        checked_url=response.url,
        snippet_found=snippet_found,
        snippet_version=domain.snippet_version if domain else None,
        heartbeat_seen=heartbeat_seen,
        heartbeat_at=heartbeat_at,
        og_title=scan["og_title"],
        og_image=scan["og_image"],
        has_own_og_tags=bool(scan["og_title"] and scan["og_image"]),
        status="installed" if installed else "not_found",
        message=message,
        hint=hint,
    )


# ---------------------------------------------------------------------------
# Heartbeat (public, called by the snippet itself)
# ---------------------------------------------------------------------------


@public_router.get("/ping", status_code=status.HTTP_204_NO_CONTENT)
@public_router.post("/ping", status_code=status.HTTP_204_NO_CONTENT)
def install_ping(
    request: Request,
    host: str = Query(..., max_length=253, description="Host the snippet is running on"),
    v: Optional[str] = Query(None, max_length=32, description="Snippet version"),
    db: Session = Depends(get_db),
):
    """Record that the snippet is alive on a domain.

    Unauthenticated by necessity — it is called from the customer's own site. It
    only ever touches a domain that already exists, and writes nothing an
    attacker could read back, so the worst a forged ping can do is refresh a
    timestamp on a domain that is already connected.
    """
    client_ip = get_client_ip(request)
    if not check_rate_limit(get_rate_limit_key_for_ip(client_ip, "install_ping"), limit=60, window_seconds=300):
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    hostname = _normalize_host(host)
    if not hostname:
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        domain = db.query(DomainModel).filter(DomainModel.name == hostname).first()
        if domain:
            now = datetime.utcnow()
            if domain.snippet_installed_at is None:
                domain.snippet_installed_at = now
            domain.snippet_last_seen_at = now
            if v:
                domain.snippet_version = v
            db.commit()
    except Exception as exc:  # pragma: no cover - a failed heartbeat must stay silent
        logger.warning("Install ping failed for %s: %s", hostname, exc)
        db.rollback()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# One-click install artifacts
# ---------------------------------------------------------------------------


def _php_escape(value: str) -> str:
    """Escape a value for a PHP single-quoted string literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


def _wordpress_plugin_source(domain_name: str) -> str:
    snippet_url = _php_escape(_snippet_url())
    site = _php_escape(domain_name)
    return f"""<?php
/**
 * Plugin Name: MyMetaView Previews
 * Plugin URI:  https://mymetaview.com
 * Description: Adds the MyMetaView snippet to your site so shared links render rich preview cards.
 * Version:     {SNIPPET_VERSION}
 * Author:      MyMetaView
 * License:     GPLv2 or later
 */

if ( ! defined( 'ABSPATH' ) ) {{
    exit;
}}

define( 'MYMETAVIEW_SNIPPET_URL', '{snippet_url}' );
define( 'MYMETAVIEW_SITE', '{site}' );

/**
 * Print the snippet as early in <head> as WordPress allows, so crawlers that
 * only read the first part of the document still see it.
 */
function mymetaview_print_snippet() {{
    printf(
        '<script src="%s" data-site="%s" defer></script>' . "\\n",
        esc_url( MYMETAVIEW_SNIPPET_URL ),
        esc_attr( MYMETAVIEW_SITE )
    );
}}
add_action( 'wp_head', 'mymetaview_print_snippet', 1 );

/**
 * Point admins at the dashboard from the plugins list.
 */
function mymetaview_action_links( $links ) {{
    $links[] = '<a href="https://mymetaview.com/app/install" target="_blank" rel="noopener">Dashboard</a>';
    return $links;
}}
add_filter( 'plugin_action_links_' . plugin_basename( __FILE__ ), 'mymetaview_action_links' );
"""


def _wordpress_readme(domain_name: str) -> str:
    return f"""=== MyMetaView Previews ===
Stable tag: {SNIPPET_VERSION}

Adds the MyMetaView snippet to {domain_name}.

== Installation ==

1. In WordPress, go to Plugins > Add New > Upload Plugin.
2. Upload this zip file and click Install Now.
3. Click Activate.

That is the whole setup. There are no settings to configure — the plugin is
already bound to {domain_name}.

To confirm it worked, open the Install page in your MyMetaView dashboard and
click "Check installation".
"""


@router.get("/downloads/wordpress-plugin")
def download_wordpress_plugin(
    domain_id: Optional[int] = Query(None),
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """A ready-to-upload WordPress plugin, pre-bound to the domain."""
    target = _resolve_target_domain(db, current_org, domain_id, domain)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "mymetaview-previews/mymetaview-previews.php",
            _wordpress_plugin_source(target.name),
        )
        archive.writestr("mymetaview-previews/readme.txt", _wordpress_readme(target.name))
    buffer.seek(0)

    return Response(
        content=buffer.read(),
        media_type="application/zip",
        headers={
            "Content-Disposition": 'attachment; filename="mymetaview-previews.zip"',
            "Cache-Control": "no-store",
        },
    )


@router.get("/downloads/gtm-container")
def download_gtm_container(
    domain_id: Optional[int] = Query(None),
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """A Google Tag Manager container the customer imports in one step."""
    target = _resolve_target_domain(db, current_org, domain_id, domain)

    container = {
        "exportFormatVersion": 2,
        "containerVersion": {
            "name": "MyMetaView Previews",
            "description": f"Adds the MyMetaView snippet to {target.name}.",
            "container": {"name": "MyMetaView Previews", "usageContext": ["WEB"]},
            "tag": [
                {
                    "name": "MyMetaView Snippet",
                    "type": "html",
                    "parameter": [
                        {
                            "type": "TEMPLATE",
                            "key": "html",
                            "value": _snippet_tag(target.name),
                        },
                        {"type": "BOOLEAN", "key": "supportDocumentWrite", "value": "false"},
                    ],
                    # 2147479553 is GTM's built-in "All Pages" trigger.
                    "firingTriggerId": ["2147479553"],
                    "tagFiringOption": "ONCE_PER_EVENT",
                }
            ],
        },
    }

    return Response(
        content=json.dumps(container, indent=2),
        media_type="application/json",
        headers={
            "Content-Disposition": 'attachment; filename="mymetaview-gtm-container.json"',
            "Cache-Control": "no-store",
        },
    )


def _cloudflare_worker_source(domain_name: str) -> str:
    api_origin = _public_origin()
    return f"""/**
 * MyMetaView edge injector for {domain_name}
 *
 * Deploy this in front of your site and social crawlers get real Open Graph
 * tags in the HTML they receive. Unlike the browser snippet, this works for
 * crawlers that do not execute JavaScript — which is most of them.
 *
 * Deploy:
 *   1. Cloudflare dashboard > Workers & Pages > Create > Worker
 *   2. Paste this file, click Deploy
 *   3. Add a route for {domain_name}/* pointing at the worker
 */

const API_ORIGIN = '{api_origin}';
const SITE = '{domain_name}';

// Crawlers that read Open Graph tags but never run JavaScript.
const CRAWLER_PATTERN = /(facebookexternalhit|facebookcatalog|Twitterbot|LinkedInBot|Slackbot|Discordbot|WhatsApp|TelegramBot|Pinterest|redditbot|Applebot|SkypeUriPreview|vkShare|W3C_Validator|Iframely|Embedly)/i;

function escapeHtml(value) {{
  return String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}}

const OG_TYPES = {{ product: 'product', blog: 'article', landing: 'website' }};

async function loadPreview(url) {{
  const endpoint = API_ORIGIN + '/api/v1/public/preview?full_url=' +
    encodeURIComponent(url) + '&site=' + encodeURIComponent(SITE);
  const res = await fetch(endpoint, {{
    cf: {{ cacheTtl: 300, cacheEverything: true }},
  }});
  if (!res.ok) return null;
  const data = await res.json();
  return data && data.title ? data : null;
}}

class HeadInjector {{
  constructor(preview, url) {{
    this.preview = preview;
    this.url = url;
  }}

  element(head) {{
    const p = this.preview;
    const tags = [
      ['og:url', p.url || this.url],
      ['og:title', p.title],
      ['og:description', p.description || ''],
      ['og:type', OG_TYPES[p.type] || 'website'],
      ['og:image', p.image_url],
      ['og:site_name', p.site_name],
    ];
    const nameTags = [
      ['twitter:card', 'summary_large_image'],
      ['twitter:title', p.title],
      ['twitter:description', p.description || ''],
      ['twitter:image', p.image_url],
    ];

    let html = '';
    for (const [key, value] of tags) {{
      if (value) html += '<meta property="' + key + '" content="' + escapeHtml(value) + '">';
    }}
    for (const [key, value] of nameTags) {{
      if (value) html += '<meta name="' + key + '" content="' + escapeHtml(value) + '">';
    }}

    // Prepended so these win over anything the origin emits later in <head>.
    head.prepend(html, {{ html: true }});
  }}
}}

export default {{
  async fetch(request) {{
    const response = await fetch(request);

    const userAgent = request.headers.get('user-agent') || '';
    if (!CRAWLER_PATTERN.test(userAgent)) return response;

    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('text/html')) return response;

    let preview;
    try {{
      preview = await loadPreview(request.url);
    }} catch (err) {{
      return response;
    }}
    if (!preview) return response;

    return new HTMLRewriter()
      .on('head', new HeadInjector(preview, request.url))
      .transform(response);
  }},
}};
"""


@router.get("/downloads/cloudflare-worker")
def download_cloudflare_worker(
    domain_id: Optional[int] = Query(None),
    domain: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    current_org: Organization = Depends(get_current_org),
):
    """An edge worker that injects tags server-side, for crawlers that ignore JS."""
    target = _resolve_target_domain(db, current_org, domain_id, domain)

    return Response(
        content=_cloudflare_worker_source(target.name),
        media_type="application/javascript",
        headers={
            "Content-Disposition": 'attachment; filename="mymetaview-worker.js"',
            "Cache-Control": "no-store",
        },
    )
