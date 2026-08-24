"""SSRF guard for user-influenced fetches.

The engine takes a URL from a form field and fetches it from inside our
network. Without a check, ``http://169.254.169.254/latest/meta-data/`` is a
valid preview target and the card comes back holding cloud credentials; so is
``http://10.0.0.5:6379`` and any other service that answers on a private
address.

The guard is deliberately allow-by-default for the public internet and
deny-by-default for everything else: we resolve the hostname and reject if
*any* resolved address is private, loopback, link-local, multicast, reserved,
or otherwise not globally routable. Resolving every address (rather than the
first) is what stops a DNS record that returns one public and one private A
record from sneaking through.

This does not close the TOCTOU window — DNS can change between our resolution
and the socket connect. Closing it fully needs a pinned-IP connection adapter;
``session.py`` pins the resolved address for direct fetches where it can, and
re-guards on every redirect hop, which covers the realistic attack.
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Set
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SSRFError(ValueError):
    """A URL was refused because it points somewhere we must not fetch."""


@dataclass(frozen=True)
class UrlPolicy:
    """What counts as a fetchable URL.

    Defaults are the production policy. Tests and the corpus runner can relax
    ``allow_private`` to hit a local fixture server without disabling the guard
    everywhere.
    """

    allowed_schemes: Set[str] = field(default_factory=lambda: {"http", "https"})
    # Ports that are plainly not web servers are refused outright; anything else
    # is allowed because plenty of legitimate sites run on odd ports.
    denied_ports: Set[int] = field(default_factory=lambda: {
        22, 23, 25, 110, 143, 445, 465, 587, 993, 995,
        1433, 3306, 3389, 5432, 5900, 6379, 9200, 11211, 27017,
    })
    allow_private: bool = False
    max_redirects: int = 5


DEFAULT_POLICY = UrlPolicy()

# Hostnames that never resolve anywhere useful and are common SSRF probes.
_DENIED_HOSTNAMES = {
    "localhost",
    "localhost.localdomain",
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
}


def _addresses_for(host: str) -> List[str]:
    """Every address the hostname resolves to, v4 and v6.

    A literal IP resolves to itself without touching DNS.
    """
    try:
        ipaddress.ip_address(host)
        return [host]
    except ValueError:
        pass
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return sorted({info[4][0] for info in infos})


def _is_public_address(addr: str) -> bool:
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def is_public_host(host: str) -> bool:
    """True when every address ``host`` resolves to is globally routable."""
    try:
        addresses = _addresses_for(host)
    except socket.gaierror:
        return False
    return bool(addresses) and all(_is_public_address(a) for a in addresses)


def guard_url(
    url: str,
    *,
    policy: UrlPolicy = DEFAULT_POLICY,
) -> str:
    """Return the resolved IP for ``url``, or raise ``SSRFError``.

    Callers that want to pin the connection use the returned address; callers
    that just want the check can ignore it. Either way a refusal is loud —
    silently returning ``None`` would let a caller fetch anyway.
    """
    if not url or not isinstance(url, str):
        raise SSRFError("empty url")

    parsed = urlparse(url.strip())
    scheme = (parsed.scheme or "").lower()
    if scheme not in policy.allowed_schemes:
        raise SSRFError(f"scheme not allowed: {scheme or '(none)'}")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise SSRFError("url has no host")
    if host in _DENIED_HOSTNAMES and not policy.allow_private:
        raise SSRFError(f"host not allowed: {host}")

    port = parsed.port
    if port is not None and port in policy.denied_ports:
        raise SSRFError(f"port not allowed: {port}")

    try:
        addresses = _addresses_for(host)
    except socket.gaierror as exc:
        raise SSRFError(f"dns resolution failed for {host}: {exc}") from exc

    if not addresses:
        raise SSRFError(f"dns returned no addresses for {host}")

    if not policy.allow_private:
        bad = [a for a in addresses if not _is_public_address(a)]
        if bad:
            raise SSRFError(
                f"{host} resolves to a non-public address ({bad[0]}); refusing to fetch"
            )

    return addresses[0]


def guard_all(urls: Iterable[str], *, policy: UrlPolicy = DEFAULT_POLICY) -> List[str]:
    """Filter an iterable of URLs down to the ones that pass the guard.

    Used for candidate lists (logo srcs, icon hrefs) where one bad entry should
    drop that entry rather than fail the whole extraction.
    """
    out: List[str] = []
    for url in urls:
        try:
            guard_url(url, policy=policy)
        except SSRFError as exc:
            logger.debug("SSRF guard dropped candidate %s: %s", str(url)[:120], exc)
            continue
        out.append(url)
    return out


def safe_or_none(url: Optional[str], *, policy: UrlPolicy = DEFAULT_POLICY) -> Optional[str]:
    """``url`` when it passes the guard, ``None`` when it does not."""
    if not url:
        return None
    try:
        guard_url(url, policy=policy)
    except SSRFError as exc:
        logger.info("SSRF guard refused %s: %s", str(url)[:120], exc)
        return None
    return url
