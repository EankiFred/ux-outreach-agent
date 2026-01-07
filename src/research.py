from dataclasses import asdict
from typing import Any

from openai import OpenAI

from .cache import cache_get_json, cache_set_json
from .web import fetch_pages_for_company, FetchedPage

client = OpenAI()


def summarize_company(company_name: str, pages: list[FetchedPage]) -> dict[str, Any]:
    """Turn fetched pages into a short structured company profile."""
    sources = [{"url": p.url, "title": p.title} for p in pages]
    combined = "\n\n".join([f"URL: {p.url}\nTITLE: {p.title}\nTEXT: {p.text}" for p in pages])

    prompt = f"""
Du bist ein Research-Assistent. Nutze ausschließlich die folgenden Website-Auszüge, um ein Firmenprofil zu erstellen.
Wenn etwas nicht eindeutig aus dem Text hervorgeht, schreibe "Unklar".
Firma: {company_name}

Gib mir JSON mit genau diesen Feldern:
- company_summary: string (max 5 Sätze)
- what_they_sell: array of strings (3-6 bullets)
- likely_users: array of strings (2-5 bullets)
- possible_ux_opportunities: array of strings (3-6 bullets, konkret)
- confidence: number (0-100) wie sicher du bist
- uncertainties: array of strings (0-5 bullets)
- sources: array of objects {{url, title}} (nimm die URLs aus dem Input)

Website-Auszüge:
{combined}
""".strip()

    resp = client.responses.create(
        model="gpt-5-mini",
        input=prompt,
    )
    text = resp.output_text.strip()

    # Robust: return raw even if model doesn't output perfect JSON
    return {
        "company_name": company_name,
        "profile_raw": text,
        "sources": sources,
    }


def build_company_profile(company_name: str, company_url: str, use_cache: bool = True) -> dict[str, Any]:
    """Fetch pages -> summarize via LLM -> cache result."""
    cache_key = f"profile::{company_name}::{company_url}"
    if use_cache:
        cached = cache_get_json("cache/profiles", cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

    pages = fetch_pages_for_company(company_url, max_pages=5)

    # IMPORTANT: do not store HTML in profile caches (size + noise)
    pages_dict = [{"url": p.url, "title": p.title, "text": p.text} for p in pages]

    result = summarize_company(company_name, pages)
    result["pages"] = pages_dict
    result["from_cache"] = False
    cache_set_json("cache/profiles", cache_key, result)
    return result
