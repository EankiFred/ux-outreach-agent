from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

import pandas as pd

from .types import SearchSpec


# ----------------------------
# Utilities
# ----------------------------
def _safe_parse_json(text: str) -> Dict[str, Any]:
    if not text:
        return {}
    t = text.strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def _has_any(text: str, keywords: List[str]) -> bool:
    t = _norm(text)
    return any(k.lower() in t for k in keywords if k and k.strip())


def _bucket_from_score(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "promising"
    if score >= 40:
        return "maybe"
    return "weak"


# ----------------------------
# Heuristic keyword sets (EN + DE)
# ----------------------------
CONSUMER_LOCAL_SERVICE_HINTS = [
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
    "fitness studio",
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
    "studio",
    "tattoo",
    "hotel",
    "gasthaus",
]

B2B_HINTS = [
    # EN
    "b2b",
    "enterprise",
    "industrial",
    "manufacturing",
    "engineering",
    "logistics",
    "supply chain",
    "operations",
    "maintenance",
    "service",
    "automation",
    "compliance",
    "quality management",
    "procurement",
    "erp",
    # DE
    "b2b",
    "industrie",
    "fertigung",
    "maschinenbau",
    "logistik",
    "lieferkette",
    "betrieb",
    "service",
    "wartung",
    "instandhaltung",
    "automatisierung",
    "qualitätsmanagement",
    "beschaffung",
    "erp",
]

SOFTWARE_PRODUCT_HINTS = [
    "saas",
    "software",
    "platform",
    "api",
    "integrations",
    "sdk",
    "cloud",
    "developer",
    "graphql",
    "typescript",
    # DE
    "software",
    "plattform",
    "api",
    "integrationen",
    "sdk",
    "cloud",
]


def _score_from_text(text: str, spec: SearchSpec) -> Tuple[int, List[str]]:
    """
    Scores how promising a lead looks for decision-support prototypes.
    Heuristic + explainable on purpose.
    """
    reasons: List[str] = []
    t = _norm(text)

    score = 35  # baseline

    # Negative: local consumer services
    if spec.exclude_consumer_services and _has_any(t, CONSUMER_LOCAL_SERVICE_HINTS):
        score -= 45
        reasons.append("Looks like a local consumer service (excluded).")

    # Positive: B2B / industrial ops signals
    if spec.prefer_b2b and _has_any(t, B2B_HINTS):
        score += 20
        reasons.append("Contains B2B / industrial / ops keywords.")

    # Positive: software orgs often fit decision-support prototypes too
    if _has_any(t, SOFTWARE_PRODUCT_HINTS):
        score += 15
        reasons.append("Contains software/platform/API signals (often good for prototypes).")

    # User-specified industry keywords (soft)
    if spec.industry_keywords:
        hits = [k for k in spec.industry_keywords if k and k.lower() in t]
        if hits:
            score += min(15, 3 * len(hits))
            reasons.append(
                f"Matches industry keywords: {', '.join(hits[:5])}" + ("…" if len(hits) > 5 else "")
            )

    score = max(0, min(100, int(score)))
    return score, reasons


def screen_leads(leads_df: pd.DataFrame, spec: SearchSpec) -> pd.DataFrame:
    rows = []
    for _, r in leads_df.iterrows():
        company_name = str(r.get("company_name", "")).strip()
        company_url = str(r.get("company_url", "")).strip()
        notes = str(r.get("notes", "")).strip()

        cheap_text = " ".join([company_name, company_url, notes])
        score, reasons = _score_from_text(cheap_text, spec)

        rows.append(
            {
                "company_name": company_name,
                "company_url": company_url,
                "screen_score": score,
                "screen_bucket": _bucket_from_score(score),
                "screen_included": score >= int(spec.min_score),
                "screen_reasons": "; ".join(reasons) if reasons else "",
            }
        )

    out = pd.DataFrame(rows)
    out = out.sort_values(by=["screen_included", "screen_score"], ascending=[False, False]).reset_index(drop=True)

    included = out[out["screen_included"] == True].copy()
    if len(included) > int(spec.max_results):
        keep_names = set(included.head(int(spec.max_results))["company_name"].tolist())
        out["screen_included"] = out.apply(
            lambda x: bool(x["screen_included"] and x["company_name"] in keep_names), axis=1
        )
        out.loc[(out["screen_included"] == False) & (out["screen_score"] >= int(spec.min_score)), "screen_reasons"] = (
            out.loc[(out["screen_included"] == False) & (out["screen_score"] >= int(spec.min_score)), "screen_reasons"]
            + "; Excluded due to max_results cap."
        )

    return out


def merge_profiles_into_screen(screen_df: pd.DataFrame, profiles: List[Dict[str, Any]], spec: SearchSpec) -> pd.DataFrame:
    by_name: Dict[str, Dict[str, Any]] = {}
    for p in profiles:
        cname = str(p.get("company_name", "")).strip()
        if cname:
            by_name[cname] = p

    rows = []
    for _, r in screen_df.iterrows():
        cname = str(r.get("company_name", "")).strip()
        base_score = int(r.get("screen_score", 0))
        base_reasons = str(r.get("screen_reasons", "")).strip()

        p = by_name.get(cname)
        if not p or p.get("error"):
            rows.append(dict(r))
            continue

        profile_raw = p.get("profile_raw", "") or ""
        parsed = _safe_parse_json(profile_raw)

        text_parts = []
        for k in ["company_summary", "what_they_sell", "likely_users", "possible_ux_opportunities", "uncertainties"]:
            v = parsed.get(k)
            if isinstance(v, str):
                text_parts.append(v)
            elif isinstance(v, list):
                text_parts.append(" ".join([str(x) for x in v if x]))
        if not text_parts:
            text_parts = [profile_raw]

        rich_text = " ".join(text_parts)
        score2, reasons2 = _score_from_text(rich_text, spec)

        blended = int(round(0.25 * base_score + 0.75 * score2))
        blended = max(0, min(100, blended))

        combined_reasons = []
        if base_reasons:
            combined_reasons.append(base_reasons)
        if reasons2:
            combined_reasons.append("Research-based: " + "; ".join(reasons2))

        row_out = dict(r)
        row_out["screen_score"] = blended
        row_out["screen_bucket"] = _bucket_from_score(blended)
        row_out["screen_included"] = blended >= int(spec.min_score)
        row_out["screen_reasons"] = " | ".join([x for x in combined_reasons if x])

        rows.append(row_out)

    out = pd.DataFrame(rows)
    out = out.sort_values(by=["screen_included", "screen_score"], ascending=[False, False]).reset_index(drop=True)

    included = out[out["screen_included"] == True].copy()
    if len(included) > int(spec.max_results):
        keep_names = set(included.head(int(spec.max_results))["company_name"].tolist())
        out["screen_included"] = out.apply(
            lambda x: bool(x["screen_included"] and x["company_name"] in keep_names), axis=1
        )
        out.loc[(out["screen_included"] == False) & (out["screen_score"] >= int(spec.min_score)), "screen_reasons"] = (
            out.loc[(out["screen_included"] == False) & (out["screen_score"] >= int(spec.min_score)), "screen_reasons"]
            + "; Excluded due to max_results cap."
        )

    return out
