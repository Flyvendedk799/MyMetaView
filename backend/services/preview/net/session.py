"""One pooled, retrying, guarded HTTP session for every engine fetch.

Before this module the engine opened a fresh TCP connection per image, used the
default ``python-requests`` UA (which Cloudflare and Akamai refuse), had no
retry on a 502, and downloaded a page's logo candidates one after another —
worst case dozens of serial round-trips inside a stage with a deadline.

``fetch`` fixes all four: connection pooling through a module-level session,
urllib3 retry/backoff on the transient statuses, the browser UA, and an SSRF
guard on the initial URL *and* every redirect hop. ``fetch_many`` runs a batch
on a small thread pool so candidate lists cost one wait instead of N.
"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from backend.services.preview.net.ssrf import SSRFError, UrlPolicy, guard_url

logger = logging.getLogger(__name__)


# The UA matters: several CDNs serve a 403 to the default requests UA, which
# read as "this site has no logo" rather than "we were turned away".
BROWSER_HEADERS: Dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 MyMetaView/3.0 "
        "(+https://mymetaview.com/bot)"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,image/avif,image/webp,image/png,"
        "image/svg+xml,image/*;q=0.8,*/*;q=0.5"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_DEFAULT_TIMEOUT = 8.0
_MAX_BYTES = 12 * 1024 * 1024  # a logo or a page; anything larger is not ours

_session: Optional[requests.Session] = None
_session_lock = threading.Lock()


def get_session() -> requests.Session:
    """The shared session. Created once, safe to use from worker threads."""
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is not None:
            return _session
        session = requests.Session()
        retry = Retry(
            total=2,
            connect=2,
            read=2,
            backoff_factor=0.4,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=frozenset({"GET", "HEAD"}),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(
            max_retries=retry,
            pool_connections=16,
            pool_maxsize=32,
        )
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        session.headers.update(BROWSER_HEADERS)
        _session = session
        return _session


def reset_session() -> None:
    """Drop the pooled session. Tests use this; production never needs it."""
    global _session
    with _session_lock:
        if _session is not None:
            try:
                _session.close()
            except Exception:  # noqa: BLE001 — closing is best-effort
                pass
        _session = None


@dataclass
class FetchResult:
    """What a guarded fetch produced. ``ok`` is the only thing callers must check."""

    url: str
    ok: bool
    status: int = 0
    content: bytes = b""
    content_type: str = ""
    error: Optional[str] = None
    refused: bool = False  # the SSRF guard said no, as distinct from a failure

    @property
    def text(self) -> str:
        try:
            return self.content.decode("utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            return ""


def fetch(
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: Optional[Dict[str, str]] = None,
    policy: UrlPolicy = UrlPolicy(),
    max_bytes: int = _MAX_BYTES,
    stream_guard: bool = True,
) -> FetchResult:
    """GET ``url`` through the shared session with the SSRF guard applied.

    Never raises for a network problem — the result carries the failure so a
    caller in a fallback chain can move on to the next candidate. A refusal by
    the guard is reported with ``refused=True`` so it is distinguishable from a
    site being down.

    Redirects are followed manually: ``requests``' own redirect handling would
    resolve the next hop itself, and that hop is exactly where an attacker
    points a public hostname at a private address.
    """
    current = url
    for hop in range(policy.max_redirects + 1):
        try:
            guard_url(current, policy=policy)
        except SSRFError as exc:
            return FetchResult(url=current, ok=False, error=str(exc), refused=True)

        try:
            response = get_session().get(
                current,
                timeout=timeout,
                headers=headers,
                allow_redirects=False,
                stream=stream_guard,
            )
        except requests.RequestException as exc:
            return FetchResult(url=current, ok=False, error=f"{type(exc).__name__}: {exc}")

        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get("location")
            response.close()
            if not location:
                return FetchResult(
                    url=current, ok=False, status=response.status_code,
                    error="redirect without location",
                )
            current = requests.compat.urljoin(current, location)
            continue

        try:
            content = _read_capped(response, max_bytes)
        except requests.RequestException as exc:
            return FetchResult(url=current, ok=False, status=response.status_code,
                               error=f"{type(exc).__name__}: {exc}")
        finally:
            response.close()

        return FetchResult(
            url=current,
            ok=response.status_code == 200 and bool(content),
            status=response.status_code,
            content=content,
            content_type=response.headers.get("content-type", "") or "",
            error=None if response.status_code == 200 else f"HTTP {response.status_code}",
        )

    return FetchResult(url=current, ok=False, error="too many redirects")


def _read_capped(response: requests.Response, max_bytes: int) -> bytes:
    """Read at most ``max_bytes``, so a hostile server can't stream us to death."""
    declared = response.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        return b""
    chunks: List[bytes] = []
    total = 0
    for chunk in response.iter_content(chunk_size=64 * 1024):
        if not chunk:
            continue
        total += len(chunk)
        if total > max_bytes:
            logger.debug("Truncating oversized response from %s", response.url)
            return b""
        chunks.append(chunk)
    return b"".join(chunks)


def fetch_many(
    urls: Sequence[str],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    headers: Optional[Dict[str, str]] = None,
    policy: UrlPolicy = UrlPolicy(),
    max_workers: int = 6,
    max_bytes: int = _MAX_BYTES,
) -> List[FetchResult]:
    """Fetch a batch concurrently, preserving input order.

    Logo-candidate resolution is the motivating case: a page can offer a dozen
    icons and the old code downloaded them one at a time inside a stage that
    has a deadline.
    """
    ordered = list(urls)
    if not ordered:
        return []
    if len(ordered) == 1:
        return [fetch(ordered[0], timeout=timeout, headers=headers,
                      policy=policy, max_bytes=max_bytes)]

    workers = max(1, min(max_workers, len(ordered)))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="pv-fetch") as pool:
        return list(pool.map(
            lambda u: fetch(u, timeout=timeout, headers=headers,
                            policy=policy, max_bytes=max_bytes),
            ordered,
        ))


def fetch_first_ok(
    urls: Iterable[str],
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    policy: UrlPolicy = UrlPolicy(),
) -> Optional[FetchResult]:
    """First candidate that came back 200 with a body, or None."""
    for result in fetch_many(list(urls), timeout=timeout, policy=policy):
        if result.ok:
            return result
    return None
