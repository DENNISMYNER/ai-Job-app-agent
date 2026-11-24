"""Polite, safe HTTP fetching for job sources.

* SSRF guard: refuses non-http(s) URLs and private/loopback addresses (unless explicitly allowed).
* robots.txt is honoured for any non-API page fetch.
* Per-host rate limiting.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from urllib import robotparser
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx

from app.core.errors import SecurityError, ValidationFailed

USER_AGENT = "LocalJobAgent/1.0 (+personal use; respects robots.txt)"
MIN_INTERVAL = 1.0  # seconds between requests to one host
_TRACKING = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "gh_src", "lever-source", "ref", "source"}

_last_hit: dict[str, float] = {}
_lock = threading.Lock()
_robots_cache: dict[str, robotparser.RobotFileParser | None] = {}

# Overridable in tests (MockTransport) and for local mock sites.
transport: httpx.BaseTransport | None = None
allow_private_hosts = False


def canonical_url(url: str) -> str:
    p = urlparse(url.strip())
    q = [(k, v) for k, v in parse_qsl(p.query) if k.lower() not in _TRACKING]
    path = p.path.rstrip("/") or "/"
    return urlunparse((p.scheme.lower(), p.netloc.lower(), path, "", urlencode(q), ""))


def assert_public_url(url: str) -> None:
    p = urlparse(url)
    if p.scheme not in {"http", "https"} or not p.hostname:
        raise ValidationFailed("Only http(s) URLs are allowed.")
    if allow_private_hosts:
        return
    try:
        infos = socket.getaddrinfo(p.hostname, None)
    except socket.gaierror as exc:
        raise ValidationFailed("Host could not be resolved.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise SecurityError("URLs pointing at private or local addresses are not allowed.")


def _throttle(host: str) -> None:
    with _lock:
        wait = _last_hit.get(host, 0) + MIN_INTERVAL - time.monotonic()
        if wait > 0 and transport is None:  # no sleeping against mocks
            time.sleep(wait)
        _last_hit[host] = time.monotonic()


def robots_allows(url: str) -> bool:
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in _robots_cache:
        rp = robotparser.RobotFileParser()
        try:
            with httpx.Client(timeout=10, transport=transport, headers={"User-Agent": USER_AGENT}) as c:
                r = c.get(f"{base}/robots.txt")
            if r.status_code == 200:
                rp.parse(r.text.splitlines())
                _robots_cache[base] = rp
            else:  # no robots.txt (404 etc.) means nothing is disallowed
                _robots_cache[base] = None
        except httpx.HTTPError:
            _robots_cache[base] = None
    rp = _robots_cache[base]
    return True if rp is None else rp.can_fetch(USER_AGENT, url)


def fetch(url: str, *, respect_robots: bool = True, accept: str = "text/html,application/json,*/*") -> httpx.Response:
    assert_public_url(url)
    if respect_robots and not robots_allows(url):
        raise SecurityError("This site's robots.txt disallows automated access. Use manual import instead.")
    _throttle(urlparse(url).netloc)
    try:
        with httpx.Client(
            timeout=20, follow_redirects=False, transport=transport,
            headers={"User-Agent": USER_AGENT, "Accept": accept},
        ) as c:
            r = c.get(url)
            hops = 0
            while r.is_redirect and hops < 3:  # re-validate every redirect target
                nxt = str(r.next_request.url) if r.next_request else ""
                assert_public_url(nxt)
                r = c.get(nxt)
                hops += 1
    except httpx.HTTPError as exc:
        raise ValidationFailed(f"Could not fetch the page: {type(exc).__name__}") from exc
    if r.status_code in (401, 403, 429):
        raise SecurityError(f"The site refused automated access (HTTP {r.status_code}).")
    r.raise_for_status()
    if len(r.content) > 3_000_000:
        raise ValidationFailed("Page is too large to import.")
    return r


def reset_caches() -> None:
    _robots_cache.clear()
    _last_hit.clear()
