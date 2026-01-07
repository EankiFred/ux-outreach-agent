import json
import hashlib
import re
from typing import Any, Dict, Optional

from openai import OpenAI

from .cache import cache_get_json, cache_set_json

client = OpenAI()

FIT_VERSION = "v3"  # bump when logic/prompt changes


FIT_PROMPT_TEMPLATE = """
Du bist ein Senior AI-Consultant.
Ziel: Bewerte, ob sich diese Firma für einen **Agentic Decision-Support Prototyp** eignet
(nicht Automatisierung, sondern Entscheidungs-Vorbereitung).

WICHTIG: Du bewertest streng und pragmatisch. Wenn Infos fehlen, ist das normal.
Setze den Score NICHT automatisch auf 0, außer wenn die Firma offensichtlich keine geeignete Daten-/Entscheidungsdomäne hat
(z.B. lokaler Consumer-Service ohne operative Daten/Prozesse in relevanter Tiefe).

USER-PREFERENCES (steuern den Fokus):
- decision_goal: {decision_goal}
- risk_tolerance: {risk_tolerance}
- prototype_horizon: {prototype_horizon}
- detail_level: {detail_level}

INPUT (bereits recherchiert; kann JSON oder Text sein):
{company_profile}

KRITERIEN:
1) Gibt es wiederkehrende, nicht-triviale Entscheidungen? (Stakeholder, Abwägungen, Unsicherheit)
2) Gibt es plausible Datenquellen/Signale? (Tools, Prozesse, Systeme, Logs, Telemetrie, Workflows)
3) Ist ein Prototyp in {prototype_horizon} realistisch ohne massive Integration?
4) Risiko & Constraints passend zur Risk-Tolerance ({risk_tolerance})?
5) Kann man einen klaren Use-Case formulieren, der "Decision Support" ist (Explainability, Human-in-the-loop)?

GIB JSON zurück mit GENAU diesen Feldern:
- fit_score: number (0-100)
- decision_summary: string (2-3 Sätze, management-tauglich)
- why_good_fit: array of strings (max 5, konkret)
- why_not: array of strings (0-4, ehrlich)
- recommended_use_case: string (ein klarer Decision-Support Use-Case, {prototype_horizon})
- target_roles: array of strings (1-3 Rollen, strategisch)
- missing_critical_info: boolean
- next_questions: array of strings (0-5, die 5 wichtigsten Fragen)

REGELN:
- Erfinde keine Fakten.
- Kein Marketing-Sprech.
- Wenn der Input klar nach lokalem Consumer-Service aussieht: fit_score eher niedrig und ehrlich begründen.
""".strip()


# Hard negative keywords (EN/DE) for local consumer services
LOCAL_CONSUMER_HINTS = [
    "salon",
    "hair",
    "barber",
    "restaurant",
    "cafe",
    "bakery",
    "spa",
    "nails",
    "tattoo",
    "gym",
    "hotel",
    "friseur",
    "barbier",
    "kosmetik",
    "nagel",
    "tattoo",
    "gasthaus",
    "würzburg",
    "wuerzburg",
    "öffnungszeiten",
    "oeffnungszeiten",
]


def _safe_parse_json(text: str) -> Dict[str, Any]:
    t = (text or "").strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else {"raw": t}
    except Exception:
        pass

    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = t[start : end + 1]
        try:
            obj = json.loads(candidate)
            return obj if isinstance(obj, dict) else {"raw": t}
        except Exception:
            return {"raw": t}

    return {"raw": t}


def _hash_profile(profile_raw: str) -> str:
    return hashlib.sha256((profile_raw or "").encode("utf-8")).hexdigest()[:12]


def _looks_like_local_consumer_service(profile_raw: str) -> bool:
    t = (profile_raw or "").lower()
    hits = sum(1 for k in LOCAL_CONSUMER_HINTS if k in t)
    return hits >= 2  # require multiple hints to avoid false positives


def _apply_hard_guard(
    parsed: Dict[str, Any],
    profile_raw: str,
    exclude_local_services: bool,
) -> Dict[str, Any]:
    """
    If the user wants to exclude local consumer services and the profile looks like one,
    clamp score hard and rewrite summary/use-case to be honest.
    """
    if not exclude_local_services:
        return parsed

    if not _looks_like_local_consumer_service(profile_raw):
        return parsed

    # Clamp score
    score = parsed.get("fit_score")
    if not isinstance(score, (int, float)):
        score = 15
    score = int(max(0, min(25, score)))  # hard cap

    parsed["fit_score"] = score
    parsed["missing_critical_info"] = True

    # Provide a clear, consistent narrative
    if not parsed.get("decision_summary"):
        parsed["decision_summary"] = (
            "Wirkt wie ein lokaler Consumer-Service mit begrenzter Daten-/Entscheidungskomplexität. "
            "Für einen Agentic Decision-Support Prototyp ist der erwartete Hebel im Verhältnis zum Aufwand gering."
        )

    # If model proposed some fancy use-case, replace with a minimal/realistic one or empty
    parsed["recommended_use_case"] = (
        "Nicht empfohlen (Scope passt eher zu klassischer Termin-/Marketing-Optimierung statt agentischem Decision Support)."
    )

    # Ensure reasons match
    parsed["why_good_fit"] = [
        "Kleine Stakeholder-Zahl erlaubt schnelle Abstimmung (aber begrenzter Hebel)."
    ][:5]

    parsed["why_not"] = [
        "Begrenzte Entscheidungskomplexität und geringe Datenbasis für echten Decision Support.",
        "Der Use-Case wäre eher klassische Automatisierung/CRM/Booking-Optimierung als agentische Entscheidungsvorbereitung.",
    ][:4]

    parsed["target_roles"] = ["Owner / Management"]

    parsed["next_questions"] = [
        "Gibt es überhaupt strukturierte Daten (Booking/POS/CRM) und echten Entscheidungsdruck jenseits Terminplanung?",
        "Was wäre der messbare Business-Hebel, der einen Prototyp rechtfertigt?",
    ][:5]

    return parsed


def score_company_fit(
    company_name: str,
    profile_raw: str,
    preferences: Optional[Dict[str, Any]] = None,
    use_cache: bool = True,
) -> Dict[str, Any]:
    """
    Decision suitability scoring for agentic decision-support (not outreach).
    - Preferences influence the prompt (goal/risk/horizon/detail).
    - Hard-guard clamps obvious local consumer services if user chose to exclude them.
    - Cache is keyed by (version + company + profile hash + preferences hash).
    """
    preferences = preferences or {}
    profile_hash = _hash_profile(profile_raw)

    # Preferences hash to avoid weird "same company but different settings" cache collisions
    pref_str = json.dumps(preferences, sort_keys=True, ensure_ascii=False)
    pref_hash = hashlib.sha256(pref_str.encode("utf-8")).hexdigest()[:10]

    cache_key = f"fit::{FIT_VERSION}::{company_name}::{profile_hash}::{pref_hash}"

    if use_cache:
        cached = cache_get_json("cache/fit", cache_key)
        if cached:
            cached["from_cache"] = True
            return cached

    prompt = FIT_PROMPT_TEMPLATE.format(
        decision_goal=str(preferences.get("decision_goal", "General decision-support (broad)")),
        risk_tolerance=str(preferences.get("risk_tolerance", "Medium")),
        prototype_horizon=str(preferences.get("prototype_horizon", "2–4 weeks (strict)")),
        detail_level=str(preferences.get("detail_level", "Standard")),
        company_profile=profile_raw,
    )

    resp = client.responses.create(model="gpt-5-mini", input=prompt)
    text = (resp.output_text or "").strip()
    parsed = _safe_parse_json(text)

    if not isinstance(parsed, dict):
        parsed = {"raw": text}

    # Normalize + defaults
    score = parsed.get("fit_score")
    if not isinstance(score, (int, float)):
        # neutral default if model misbehaves
        parsed["fit_score"] = 50
    parsed["fit_score"] = int(max(0, min(100, int(parsed.get("fit_score", 0)))))

    # Hard guard for local consumer services when excluded
    parsed = _apply_hard_guard(
        parsed=parsed,
        profile_raw=profile_raw,
        exclude_local_services=bool(preferences.get("exclude_local_services", True)),
    )

    result: Dict[str, Any] = {
        "company_name": company_name,
        "fit": parsed,
        "fit_raw": text,
        "from_cache": False,
        "preferences": preferences,
    }

    cache_set_json("cache/fit", cache_key, result)
    return result
