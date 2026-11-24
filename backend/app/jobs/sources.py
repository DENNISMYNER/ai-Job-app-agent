"""Job source adapters. Each returns a list of normalised ``RawJob`` dicts.

Only legitimate, permitted interfaces are used: Greenhouse and Lever public board
APIs, RSS feeds, public career pages (robots.txt respected) and manual URLs.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from typing import TypedDict
from urllib.parse import urljoin

import feedparser
from bs4 import BeautifulSoup

from app.core.errors import ValidationFailed
from app.jobs import http
from app.security.untrusted import html_to_text


class RawJob(TypedDict, total=False):
    external_id: str
    title: str
    company: str
    location: str
    url: str
    description: str
    employment_type: str
    posted_at: datetime | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str


def _dt_ms(ms) -> datetime | None:
    try:
        return datetime.fromtimestamp(int(ms) / 1000, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _dt_iso(s) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def fetch_greenhouse(board_token: str, company: str = "") -> list[RawJob]:
    token = re.sub(r"[^A-Za-z0-9_-]", "", board_token)
    if not token:
        raise ValidationFailed("Invalid Greenhouse board token.")
    r = http.fetch(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true", respect_robots=False)
    out: list[RawJob] = []
    for j in r.json().get("jobs", []):
        out.append(
            RawJob(
                external_id=str(j.get("id")),
                title=j.get("title", ""),
                company=company or token,
                location=(j.get("location") or {}).get("name", ""),
                url=j.get("absolute_url", ""),
                description=html_to_text(unescape(j.get("content", ""))),
                posted_at=_dt_iso(j.get("updated_at")),
            )
        )
    return out


def fetch_lever(company_slug: str, company: str = "") -> list[RawJob]:
    slug = re.sub(r"[^A-Za-z0-9_-]", "", company_slug)
    if not slug:
        raise ValidationFailed("Invalid Lever company slug.")
    r = http.fetch(f"https://api.lever.co/v0/postings/{slug}?mode=json", respect_robots=False)
    out: list[RawJob] = []
    for j in r.json():
        cats = j.get("categories") or {}
        out.append(
            RawJob(
                external_id=str(j.get("id")),
                title=j.get("text", ""),
                company=company or slug,
                location=cats.get("location", "") or "",
                employment_type=(cats.get("commitment") or "").lower(),
                url=j.get("hostedUrl", ""),
                description=html_to_text(j.get("descriptionPlain") or j.get("description", "")),
                posted_at=_dt_ms(j.get("createdAt")),
            )
        )
    return out


def fetch_rss(feed_url: str, company: str = "") -> list[RawJob]:
    r = http.fetch(feed_url, accept="application/rss+xml,application/xml,text/xml,*/*")
    feed = feedparser.parse(r.content)
    out: list[RawJob] = []
    for e in feed.entries:
        link = e.get("link", "")
        if not link:
            continue
        posted = None
        if e.get("published_parsed"):
            posted = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        out.append(
            RawJob(
                external_id=e.get("id") or link,
                title=html_to_text(e.get("title", "")),
                company=company or html_to_text(e.get("author", "")) or feed.feed.get("title", ""),
                location=e.get("location", ""),
                url=link,
                description=html_to_text(e.get("summary", "") or (e.get("content") or [{}])[0].get("value", "")),
                posted_at=posted,
            )
        )
    return out


def parse_job_page(html: str, url: str, company: str = "") -> RawJob:
    """Parse one job posting page: prefer schema.org JSON-LD, fall back to headings/body."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except ValueError:
            continue
        for item in data if isinstance(data, list) else [data]:
            if isinstance(item, dict) and item.get("@type") == "JobPosting":
                loc = item.get("jobLocation") or {}
                if isinstance(loc, list):
                    loc = loc[0] if loc else {}
                addr = (loc.get("address") or {}) if isinstance(loc, dict) else {}
                org = item.get("hiringOrganization") or {}
                sal = ((item.get("baseSalary") or {}).get("value") or {}) if isinstance(item.get("baseSalary"), dict) else {}
                return RawJob(
                    external_id=url,
                    title=html_to_text(item.get("title", "")),
                    company=company or (org.get("name", "") if isinstance(org, dict) else str(org)),
                    location=", ".join(x for x in [addr.get("addressLocality"), addr.get("addressCountry")] if isinstance(x, str) and x)
                    or ("Remote" if item.get("jobLocationType") == "TELECOMMUTE" else ""),
                    url=url,
                    description=html_to_text(item.get("description", "")),
                    employment_type=str(item.get("employmentType") or "").lower().replace("_", "-"),
                    posted_at=_dt_iso(item.get("datePosted")) if item.get("datePosted") else None,
                    salary_min=int(sal["minValue"]) if isinstance(sal, dict) and sal.get("minValue") else None,
                    salary_max=int(sal["maxValue"]) if isinstance(sal, dict) and sal.get("maxValue") else None,
                    salary_currency=(item.get("baseSalary") or {}).get("currency", "") if isinstance(item.get("baseSalary"), dict) else "",
                )
    title = (soup.find("h1") or soup.find("title"))
    body = soup.find("main") or soup.find("article") or soup.body or soup
    return RawJob(
        external_id=url, title=title.get_text(" ", strip=True) if title else "Untitled role",
        company=company, location="", url=url, description=html_to_text(str(body)),
    )


def fetch_career_page(page_url: str, company: str = "") -> list[RawJob]:
    """Index page -> follow same-site links that look like job postings (max 25)."""
    r = http.fetch(page_url)
    soup = BeautifulSoup(r.text, "html.parser")
    jobs: list[RawJob] = []
    seen: set[str] = set()
    base_host = http.urlparse(page_url).netloc
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"])
        if http.urlparse(href).netloc != base_host or href in seen:
            continue
        if re.search(r"/(jobs?|careers?|positions?|openings?|roles?)/[^/]+", href, re.I) and href.rstrip("/") != page_url.rstrip("/"):
            seen.add(href)
            if len(seen) > 25:
                break
            try:
                jobs.append(parse_job_page(http.fetch(href).text, href, company))
            except Exception:  # one broken posting must not abort the run
                continue
    return jobs


def fetch_manual(url: str, company: str = "") -> list[RawJob]:
    return [parse_job_page(http.fetch(url).text, url, company)]


ADAPTERS = {
    "greenhouse": fetch_greenhouse,
    "lever": fetch_lever,
    "rss": fetch_rss,
    "career_page": fetch_career_page,
    "manual": fetch_manual,
}
