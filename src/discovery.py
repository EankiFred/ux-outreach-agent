# src/discovery.py
from __future__ import annotations
from urllib.parse import urlparse, parse_qs, unquote, quote_plus


import re
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse, quote_plus

import requests
from bs4 import BeautifulSoup


# ----------------------------
# Types
# ----------------------------
@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""


@dataclass
class DiscoverySpec:
    industry: str = ""
    keywords: str = ""
    country: str = ""
    region_or_city: str = ""
    company_size: str = ""  # e.g. "1-10", "11-50", "51-200", "201-1000", "1000+"
    exclude_consumer_services: bool = True


# ----------------------------
# Utilities
# ----------------------------
def _norm(s: str) -> str:
    return " ".join(str(s or "").strip().split())


def _clean_title(title: str) -> str:
    t = _norm(title)
    # remove common suffixes (very rough)
    t = re.sub(r"\s*[-–|]\s*(LinkedIn|Xing|Crunchbase|Wikipedia|Jobs|Karriere|Careers)\s*$", "", t, flags=re.I)
    return t.strip()


def _is_probably_company_domain(url: str) -> bool:
    if not url:
        return False
    try:
        u = urlparse(url)
        if u.scheme not in {"http", "https"}:
            return False
        host = (u.netloc or "").lower()
        if not host or "." not in host:
            return False
        # avoid obvious non-company hosts (still imperfect)
        bad_hosts = [
            "linkedin.com",
            "xing.com",
            "crunchbase.com",
            "wikipedia.org",
            "facebook.com",
            "instagram.com",
            "youtube.com",
            "twitter.com",
            "x.com",
            "github.com",
            "apps.apple.com",
            "play.google.com",
        ]
        if any(host.endswith(b) for b in bad_hosts):
            return False
        return True
    except Exception:
        return False


def _looks_like_consumer_service(text: str) -> bool:
    t = _norm(text).lower()
    hints = [
        # EN
        "salon",
        "hair",
        "barber",
        "restaurant",
        "cafe",
        "bakery",
        "beauty",
        "spa",
        "nails",
        "tattoo",
        "gym",
        "hotel",
        # DE
        "friseur",
        "barbier",
        "restaurant",
        "café",
        "baeckerei",
        "bäckerei",
        "kosmetik",
        "nagel",
        "tattoo",
        "hotel",
        "gasthaus",
        "öffnungszeiten",
        "oeffnungszeiten",
    ]
    hits = sum(1 for h in hints if h in t)
    return hits >= 2


# ----------------------------
# DuckDuckGo HTML search (no key)
# ----------------------------
# src/discovery.py (PATCH)
from urllib.parse import urlparse, parse_qs, unquote, quote_plus

def _unwrap_ddg_url(href: str) -> str:
    """
    DDG often returns redirect URLs like:
    https://duckduckgo.com/l/?uddg=https%3A%2F%2Flinear.app%2F
    We unwrap them to the real target URL.
    """
    if not href:
        return href

    try:
        u = urlparse(href)
        # DDG redirect pattern
        if "duckduckgo.com" in (u.netloc or "") and u.path.startswith("/l/"):
            qs = parse_qs(u.query or "")
            if "uddg" in qs and qs["uddg"]:
                return unquote(qs["uddg"][0])
    except Exception:
        pass

    return href


def _request_html(url: str, timeout_s: int = 12) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        ),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
        "Referer": "https://duckduckgo.com/",
    }
    r = requests.get(url, headers=headers, timeout=timeout_s)
    if r.status_code >= 400:
        return ""
    return r.text or ""


def _ddg_search(query: str, max_results: int = 10, timeout_s: int = 12) -> list[SearchResult]:
    """
    More robust DDG search:
    1) Try lite.duckduckgo.com (easier to parse, fewer class changes)
    2) Fallback to duckduckgo.com/html
    Also unwrap redirect links to real target URLs.
    """
    q = _norm(query)
    if not q:
        return []

    out: list[SearchResult] = []

    # --- 1) LITE version (preferred) ---
    lite_url = "https://lite.duckduckgo.com/lite/?q=" + quote_plus(q)
    html = _request_html(lite_url, timeout_s=timeout_s)

    if html:
        soup = BeautifulSoup(html, "lxml")

        # lite results: links usually have class "result-link"
        for a in soup.select("a.result-link"):
            title = a.get_text(" ", strip=True) or ""
            href = (a.get("href") or "").strip()
            href = _unwrap_ddg_url(href)
            title = _clean_title(title)

            if href and title:
                out.append(SearchResult(title=title, url=href, snippet=""))

            if len(out) >= max_results:
                break

    # --- 2) Fallback to HTML version ---
    if len(out) == 0:
        html_url = "https://duckduckgo.com/html/?q=" + quote_plus(q)
        html2 = _request_html(html_url, timeout_s=timeout_s)

        if html2:
            soup = BeautifulSoup(html2, "lxml")
            for res in soup.select(".result"):
                a = res.select_one(".result__a")
                if not a:
                    continue

                href = (a.get("href") or "").strip()
                href = _unwrap_ddg_url(href)

                title = _clean_title(a.get_text(" ", strip=True) or "")
                snippet_el = res.select_one(".result__snippet")
                snippet = _norm(snippet_el.get_text(" ", strip=True)) if snippet_el else ""

                if href and title:
                    out.append(SearchResult(title=title, url=href, snippet=snippet))

                if len(out) >= max_results:
                    break

    return out



# ----------------------------
# Public API
# ----------------------------
def find_company_by_name(company_query: str, max_results: int = 6) -> list[dict[str, Any]]:
    """
    Given a company name (or domain), returns a list of candidates:
    [{company_name, company_url, snippet, source}]
    """
    q = _norm(company_query)
    if not q:
        return []

    # If user pasted a domain, prefer it
    if re.match(r"^https?://", q, flags=re.I) or "." in q:
        url_guess = q if q.startswith("http") else f"https://{q}"
        return [{
            "company_name": q.replace("https://", "").replace("http://", "").strip("/"),
            "company_url": url_guess,
            "snippet": "User provided URL/domain.",
            "source": "user_input",
        }]

    results = _ddg_search(f"{q} official website", max_results=max_results)
    candidates: list[dict[str, Any]] = []
    seen_hosts = set()

    for r in results:
        if not _is_probably_company_domain(r.url):
            continue
        host = urlparse(r.url).netloc.lower()
        if host in seen_hosts:
            continue
        seen_hosts.add(host)

        candidates.append({
            "company_name": r.title or q,
            "company_url": r.url,
            "snippet": r.snippet,
            "source": "ddg",
        })

    return candidates


def discover_companies(spec: DiscoverySpec, max_results: int = 10) -> list[dict[str, Any]]:
    """
    Parameter-based discovery (web search → extract company sites).
    Returns list of: {company_name, company_url, snippet, source}
    """
    parts = []
    if spec.industry:
        parts.append(spec.industry)
    if spec.keywords:
        parts.append(spec.keywords)
    if spec.region_or_city:
        parts.append(spec.region_or_city)
    if spec.country:
        parts.append(spec.country)
    if spec.company_size:
        parts.append(f'"{spec.company_size}" employees')  # weak but sometimes helps

    # Keep it simple: goal is "good enough" candidates
    query = " ".join(parts) + " company"
    query = _norm(query)

    # two queries to increase variety
    queries = [
        query,
        _norm(" ".join([spec.industry, spec.country, "B2B company"])),
    ]

    candidates: list[dict[str, Any]] = []
    seen_hosts = set()

    for q in queries:
        if not q.strip():
            continue
        results = _ddg_search(q, max_results=20)
        for r in results:
            if not _is_probably_company_domain(r.url):
                continue

            blob = f"{r.title} {r.snippet}"
            if spec.exclude_consumer_services and _looks_like_consumer_service(blob):
                continue

            host = urlparse(r.url).netloc.lower()
            if host in seen_hosts:
                continue
            seen_hosts.add(host)

            candidates.append({
                "company_name": r.title,
                "company_url": r.url,
                "snippet": r.snippet,
                "source": "ddg",
            })

            if len(candidates) >= max_results:
                break

        if len(candidates) >= max_results:
            break

        # small politeness delay
        time.sleep(0.15)

    return candidates
