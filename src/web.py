import re
import time
import os
import hashlib
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class FetchedPage:
    url: str
    title: str
    text: str
    html: str = ""  # keep raw HTML for better people extraction


def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _http_cache_dir() -> str:
    d = os.path.join(".cache", "http")
    os.makedirs(d, exist_ok=True)
    return d


def _http_cache_path(url: str) -> str:
    key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    return os.path.join(_http_cache_dir(), f"{key}.html")


def fetch_url(url: str, timeout_s: int = 12, use_cache: bool = True) -> Optional[str]:
    """
    Fetch HTML from a URL. Returns HTML string or None on error.
    Uses a small disk cache to speed up repeated runs and reduce flakiness.
    """
    if not url:
        return None

    if use_cache:
        p = _http_cache_path(url)
        if os.path.exists(p):
            try:
                return open(p, "r", encoding="utf-8", errors="ignore").read()
            except Exception:
                pass

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"
        )
    }
    try:
        r = requests.get(url, headers=headers, timeout=timeout_s, allow_redirects=True)
        if r.status_code >= 400:
            return None
        ct = (r.headers.get("content-type", "") or "").lower()
        if "text/html" not in ct:
            return None
        html = r.text

        if use_cache:
            try:
                open(_http_cache_path(url), "w", encoding="utf-8").write(html)
            except Exception:
                pass

        return html
    except Exception:
        return None


def html_to_text(html: str) -> tuple[str, str]:
    """
    Extract (title, visible text) from HTML.
    """
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    text = soup.get_text(" ", strip=True)
    return _clean_text(title), _clean_text(text)


def pick_internal_links(
    base_url: str,
    html: str,
    max_links: int = 2,
    keywords: Optional[list[str]] = None,
    block_keywords: Optional[list[str]] = None,
) -> list[str]:
    """
    Pick useful internal links. Supports keyword allowlist + blocklist.
    Generic + English/German variants.
    """
    soup = BeautifulSoup(html, "lxml")
    base = base_url.rstrip("/") + "/"
    base_netloc = urlparse(base).netloc.lower()

    if keywords is None:
        keywords = [
            # English
            "about",
            "company",
            "team",
            "leadership",
            "management",
            "imprint",
            "contact",
            "careers",
            "jobs",
            # German
            "ueber-uns",
            "über-uns",
            "uber-uns",
            "unternehmen",
            "team",
            "menschen",
            "leitung",
            "führung",
            "geschaeftsfuehrung",
            "geschäftsführung",
            "impressum",
            "kontakt",
            "karriere",
            "stellen",
            "jobs",
        ]

    if block_keywords is None:
        block_keywords = [
            "blog",
            "changelog",
            "docs",
            "documentation",
            "help",
            "press",
            "news",
            "events",
            "community",
            "privacy",
            "terms",
            "status",
            "legal",
            "security",
            "cookie",
            # common noisy sections
            "customers",
            "case-studies",
            "case-studies",
            "partners",
        ]

    candidates: list[tuple[int, str]] = []

    def score_path(path: str) -> int:
        path = path.lower()
        s = 0
        boosts = [
            ("leadership", 60),
            ("team", 55),
            ("management", 55),
            ("about", 50),
            ("company", 45),
            ("ueber-uns", 50),
            ("über-uns", 50),
            ("impressum", 45),
            ("imprint", 45),
            ("kontakt", 40),
            ("contact", 40),
            ("geschaeftsfuehrung", 55),
            ("geschäftsführung", 55),
            ("karriere", 10),
            ("careers", 10),
            ("jobs", 10),
        ]
        for k, w in boosts:
            if k in path:
                s += w
        for k in keywords:
            if k.lower() in path:
                s += 5
        for k in block_keywords:
            if k.lower() in path:
                s -= 80
        return s

    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        if not href or href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        full = urljoin(base, href)
        netloc = urlparse(full).netloc.lower()
        if netloc != base_netloc:
            continue
        path = (urlparse(full).path or "").lower()
        if not path or path == "/":
            continue
        if any(path.endswith(ext) for ext in [".pdf", ".zip", ".png", ".jpg", ".jpeg", ".svg", ".webp"]):
            continue

        s = score_path(path)
        if s <= 0:
            continue
        candidates.append((s, full))

    candidates.sort(key=lambda x: x[0], reverse=True)
    seen = set()
    uniq: list[str] = []
    for _, u in candidates:
        if u in seen:
            continue
        seen.add(u)
        uniq.append(u)
        if len(uniq) >= max_links:
            break
    return uniq


def _fetch_and_parse(
    u: str,
    timeout_s: int = 12,
    max_text: int = 18000,
    keep_html: bool = True,
) -> Optional[FetchedPage]:
    html = fetch_url(u, timeout_s=timeout_s, use_cache=True)
    if not html:
        return None
    title, text = html_to_text(html)

    low = (text or "").strip().lower()
    if low in {"loading…", "loading...", "loading"} or len(low) < 120:
        text = text[:max_text]
    else:
        text = text[:max_text]

    return FetchedPage(url=u, title=title, text=text, html=(html if keep_html else ""))


def fetch_pages_for_company(
    company_url: str,
    max_pages: int = 3,
    sleep_s: float = 0.0,
    timeout_s: int = 12,
    parallel: bool = True,
    keywords: Optional[list[str]] = None,
    block_keywords: Optional[list[str]] = None,
) -> list[FetchedPage]:
    """
    Fetch homepage + useful internal pages.
    Speed improvements:
    - disk cache for HTML
    - optional parallel fetching for internal pages
    """
    if not company_url:
        return []

    homepage_html = fetch_url(company_url, timeout_s=timeout_s, use_cache=True)
    if not homepage_html:
        return []

    urls = [company_url]
    urls.extend(
        pick_internal_links(
            company_url,
            homepage_html,
            max_links=max(0, max_pages - 1),
            keywords=keywords,
            block_keywords=block_keywords,
        )
    )

    seen = set()
    ordered: list[str] = []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        ordered.append(u)

    pages: list[FetchedPage] = []

    first = _fetch_and_parse(ordered[0], timeout_s=timeout_s)
    if first:
        pages.append(first)
    if sleep_s > 0:
        time.sleep(sleep_s)

    rest = ordered[1:max_pages]
    if not rest:
        return pages

    if not parallel or len(rest) == 1:
        for u in rest:
            p = _fetch_and_parse(u, timeout_s=timeout_s)
            if p:
                pages.append(p)
            if sleep_s > 0:
                time.sleep(sleep_s)
        return pages

    with ThreadPoolExecutor(max_workers=min(6, len(rest))) as ex:
        futs = {ex.submit(_fetch_and_parse, u, timeout_s): u for u in rest}
        for fut in as_completed(futs):
            p = fut.result()
            if p:
                pages.append(p)

    pages_sorted: list[FetchedPage] = []
    by_url = {p.url: p for p in pages}
    for u in ordered[:max_pages]:
        if u in by_url:
            pages_sorted.append(by_url[u])
    return pages_sorted
