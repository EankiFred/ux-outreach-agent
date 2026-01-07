# demo.py
import streamlit as st
import pandas as pd
import json 

from src.io import load_leads_csv
from src.research import build_company_profile
from src.fit import score_company_fit
from src.discovery import DiscoverySpec, find_company_by_name, discover_companies


# ----------------------------
# Page config (ONLY ONCE in multipage app)
# ----------------------------
st.set_page_config(
    page_title="Agentiq AI — Decision Support",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ----------------------------
# Neon / Glass UI
# ----------------------------
NEON_CSS = """
<style>
/* Hide Streamlit chrome */
#MainMenu {visibility: hidden;}
header {visibility: hidden;}
footer {visibility: hidden;}

/* =========================
   COLOR SYSTEM (mint-neon)
   ========================= */
:root{
  --ink-1: rgba(7, 22, 45, 0.92);      /* main text on light */
  --ink-2: rgba(7, 22, 45, 0.72);      /* secondary text */
  --mint-1: rgba(110,255,190,1);       /* neon mint */
  --mint-2: rgba(124,255,230,1);       /* cyan mint */
  --blue-1: rgba(122,170,255,1);       /* soft blue */
  --field-bg: rgba(7, 22, 45, 0.88);   /* dark input background */
  --field-text: rgba(230,255,248,0.98);
  --field-ph: rgba(230,255,248,0.55);
  --border-soft: rgba(140,160,190,0.28);
}

/* =========================
   GLOBAL TEXT (safe)
   ========================= */
/* DO NOT use .stApp * { ... !important }  -> breaks controls contrast */
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp div {
  color: var(--ink-1);
}
.agentiq-sub, .agentiq-step, .agentiq-hint, .stCaption, .stMarkdown p {
  color: var(--ink-2);
}

/* =========================
   APP BACKGROUND
   ========================= */
.stApp {
  background:
    radial-gradient(1200px 600px at 70% 10%, rgba(120, 255, 230, .22), transparent 60%),
    radial-gradient(900px 500px at 20% 20%, rgba(120, 170, 255, .18), transparent 55%),
    radial-gradient(1100px 700px at 50% 90%, rgba(180, 255, 220, .18), transparent 60%),
    linear-gradient(180deg, #f7fbff 0%, #eef6ff 45%, #f9fbff 100%);
}

/* =========================
   CENTERED AGENT WINDOW
   ========================= */
.agentiq-wrap {
  max-width: 980px;
  margin: 0 auto;
  padding: 28px 18px 60px 18px;
}
.agentiq-shell {
  position: relative;
  border-radius: 22px;
  background: rgba(255,255,255,0.72);
  border: 1px solid var(--border-soft);
  box-shadow:
    0 20px 70px rgba(10, 30, 60, 0.14),
    0 2px 0 rgba(255,255,255,0.6) inset;
  backdrop-filter: blur(14px);
  -webkit-backdrop-filter: blur(14px);
  overflow: hidden;
}
.agentiq-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 18px;
  border-bottom: 1px solid rgba(140, 160, 190, 0.22);
  background: linear-gradient(
    90deg,
    rgba(120,255,230,.14),
    rgba(140,255,210,.12),
    rgba(120,170,255,.08)
  );
}
.agentiq-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  font-weight: 800;
  letter-spacing: .2px;
  color: #0b1b33;
}

.agentiq-brand > div > div:first-child {
  font-size: 32px;            /* vorher klein -> jetzt deutlich */
  line-height: 1.05;
}

.agentiq-sub {
  font-size: 14px;            /* vorher 13px */
  font-weight: 650;
  opacity: 0.85;
  margin-top: 4px;
}

.agentiq-dot {
  width: 14px; height: 14px; border-radius: 999px;
  background: radial-gradient(circle at 30% 30%, #7cffe6, #5cffb3 55%, #7aaaff);
  box-shadow: 0 0 26px rgba(124,255,230,.70);
}

.agentiq-sub {
  font-size: 13px;
  margin-top: 2px;
}
.agentiq-body { padding: 18px; }

.agentiq-hint {
  padding: 12px 14px;
  border-radius: 16px;
  border: 1px solid rgba(140, 160, 190, 0.20);
  background: rgba(255,255,255,0.62);
  font-size: 14px;
}
.agentiq-step {
  font-size: 12px;
  letter-spacing: .12em;
  text-transform: uppercase;
}
.agentiq-title {
  font-size: 26px;
  font-weight: 760;
  margin: 6px 0 6px 0;
}
.agentiq-card {
  border-radius: 18px;
  border: 1px solid rgba(140,160,190,.22);
  background: rgba(255,255,255,.70);
  padding: 14px 14px;
}
.agentiq-metric {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  border: 1px solid rgba(140,160,190,.22);
  background: rgba(255,255,255,.65);
  font-size: 13px;
  color: rgba(7, 22, 45, 0.78) !important;
}

/* Fit Badges (no orange) */
.badge-strong { box-shadow: 0 0 0 2px rgba(124,255,230,.40) inset; }
.badge-promising { box-shadow: 0 0 0 2px rgba(122,170,255,.35) inset; }
.badge-maybe { box-shadow: 0 0 0 2px rgba(110,255,190,.38) inset; } /* mint */
.badge-weak { box-shadow: 0 0 0 2px rgba(180,200,220,.30) inset; }

/* =========================
   BUTTONS (fix red/orange defaults)
   ========================= */
div[data-testid="stButton"] > button {
  width: 100%;
  border-radius: 14px !important;
  padding: 10px 12px !important;
  font-weight: 750 !important;
  border: 1px solid rgba(140,160,190,.30) !important;
  background: rgba(255,255,255,.72) !important;
  color: var(--ink-1) !important;
}

/* Primary buttons (mint neon) */
div[data-testid="stButton"] > button[kind="primary"] {
  border: 1px solid rgba(110,255,190,.75) !important;
  background: linear-gradient(
    90deg,
    rgba(110,255,190,.30),
    rgba(124,255,230,.26),
    rgba(122,170,255,.18)
  ) !important;
  box-shadow: 0 8px 28px rgba(80, 255, 200, .22) !important;
  color: rgba(7, 22, 45, 0.95) !important;
}

/* Hover */
div[data-testid="stButton"] > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 32px rgba(10,30,60,.14) !important;
}

/* =========================
   INPUTS (typing color + contrast)
   ========================= */
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea {
  background: var(--field-bg) !important;
  color: var(--field-text) !important;
  border: 1px solid rgba(110,255,190,.35) !important;
  border-radius: 14px !important;
}

div[data-testid="stTextInput"] input::placeholder,
div[data-testid="stTextArea"] textarea::placeholder {
  color: var(--field-ph) !important;
}

/* Focus glow mint */
div[data-testid="stTextInput"] input:focus,
div[data-testid="stTextArea"] textarea:focus {
  box-shadow: 0 0 0 3px rgba(110,255,190,.22) !important;
  outline: none !important;
}

/* Selectbox (BaseWeb) */
div[data-testid="stSelectbox"] div[role="combobox"] {
  background: var(--field-bg) !important;
  color: var(--field-text) !important;
  border: 1px solid rgba(110,255,190,.35) !important;
  border-radius: 14px !important;
}
div[data-testid="stSelectbox"] * {
  color: var(--field-text) !important;
}

/* =========================
   SLIDER (mint)
   ========================= */
div[data-testid="stSlider"] div[data-baseweb="slider"] [data-baseweb="slider-track"] > div {
  background-color: rgba(110,255,190,.85) !important;  /* filled track */
}
div[data-testid="stSlider"] div[data-baseweb="slider"] [data-baseweb="slider-track"] {
  background-color: rgba(7, 22, 45, 0.18) !important;  /* unfilled track */
}
div[data-testid="stSlider"] div[data-baseweb="slider"] [role="slider"] {
  background-color: rgba(110,255,190, 1) !important;   /* thumb */
  box-shadow: 0 0 0 3px rgba(110,255,190,.25) !important;
}

/* =========================
   CHECKBOX / RADIO (mint accent)
   ========================= */
div[data-testid="stCheckbox"] input[type="checkbox"],
div[data-testid="stRadio"] input[type="radio"] {
  accent-color: rgba(110,255,190,1) !important;
}

/* Minor: expander header readable */
details summary, details summary * {
  color: var(--ink-1) !important;
}

/* ===== Contrast fixes for Streamlit components ===== */

/* Expander header: make always readable + light */
div[data-testid="stExpander"] details > summary {
  background: rgba(255,255,255,0.70) !important;
  border: 1px solid rgba(140,160,190,0.22) !important;
  border-radius: 14px !important;
  padding: 10px 12px !important;
}
div[data-testid="stExpander"] details > summary * {
  color: rgba(7,22,45,0.92) !important;
}

/* Info boxes: readable text */
div[data-testid="stAlert"] {
  border-radius: 14px !important;
}
div[data-testid="stAlert"] * {
  color: rgba(7,22,45,0.92) !important;
}

/* Markdown links readable */
.stMarkdown a {
  color: rgba(20, 140, 110, 0.95) !important;
}
.stMarkdown a:hover {
  text-decoration: underline;
}
</style>


"""
st.markdown(NEON_CSS, unsafe_allow_html=True)


# ----------------------------
# Helpers
# ----------------------------
def _fit_badge(score: int | None) -> tuple[str, str]:
    if score is None:
        return ("—", "badge-weak")
    if score >= 75:
        return ("Strong", "badge-strong")
    if score >= 55:
        return ("Promising", "badge-promising")
    if score >= 40:
        return ("Maybe", "badge-maybe")
    return ("Weak", "badge-weak")


def _ensure_profile(company_name: str, company_url: str, use_cache: bool) -> dict:
    if "profiles_by_name" not in st.session_state:
        st.session_state["profiles_by_name"] = {}
    if company_name in st.session_state["profiles_by_name"]:
        return st.session_state["profiles_by_name"][company_name]
    profile = build_company_profile(company_name, company_url, use_cache=use_cache)
    st.session_state["profiles_by_name"][company_name] = profile
    return profile


def _ensure_fit(company_name: str, profile_raw: str, preferences: dict, use_cache: bool) -> dict:
    if "fit_by_name" not in st.session_state:
        st.session_state["fit_by_name"] = {}
    if company_name in st.session_state["fit_by_name"]:
        return st.session_state["fit_by_name"][company_name]
    fit_state = score_company_fit(
        company_name=company_name,
        profile_raw=profile_raw,
        preferences=preferences,
        use_cache=use_cache,
    )
    st.session_state["fit_by_name"][company_name] = fit_state
    return fit_state


def _set_results(items: list[dict]):
    df = pd.DataFrame(items)
    if df.empty:
        df = pd.DataFrame(columns=["company_name", "company_url", "snippet", "source"])
    st.session_state["results_df"] = df


def _safe_parse_json_dict(text: str) -> dict:
    """
    Robust JSON parse for strings that should contain a dict.
    If parsing fails, return empty dict.
    """
    if not text:
        return {}
    t = str(text).strip()
    try:
        obj = json.loads(t)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass

    # try to salvage a JSON object inside text
    start = t.find("{")
    end = t.rfind("}")
    if start != -1 and end != -1 and end > start:
        chunk = t[start : end + 1]
        try:
            obj = json.loads(chunk)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}


def _render_company_profile_pretty(profile_state: dict):
    """
    Render the company profile in a human-friendly format.
    - Confidence metric at the top (like Suitability Score on the right)
    - Sources moved to the bottom (below Unklarheiten)
    """
    raw = str((profile_state or {}).get("profile_raw", "") or "")
    parsed = _safe_parse_json_dict(raw)

    sources = (profile_state or {}).get("sources", []) or []

    # Fallback if JSON cannot be parsed
    if not parsed:
        st.caption("Confidence")
        st.metric("Confidence", "—")
        st.markdown("#### Überblick")
        st.write(raw if raw else "Unklar.")

        if sources:
            st.markdown("#### Sources")
            for s in sources[:8]:
                st.write(f"- {s.get('title','')} — {s.get('url','')}")
        return

    summary = parsed.get("company_summary", "")
    what = parsed.get("what_they_sell", [])
    users = parsed.get("likely_users", [])
    opps = parsed.get("possible_ux_opportunities", [])
    conf = parsed.get("confidence", None)
    uncs = parsed.get("uncertainties", [])

    # --- TOP: Confidence (aligned with right column score) ---
    #st.caption("Confidence")
    if isinstance(conf, (int, float)):
        st.metric("Confidence", int(conf))
    else:
        st.metric("Confidence", "—")

    # --- Content sections ---
    if summary:
        st.markdown("#### Überblick")
        st.write(summary)

    if what:
        st.markdown("#### Was sie anbieten")
        for x in (what if isinstance(what, list) else [what])[:8]:
            if x:
                st.write(f"- {x}")

    if users:
        st.markdown("#### Wahrscheinliche Nutzer / Rollen")
        for x in (users if isinstance(users, list) else [users])[:8]:
            if x:
                st.write(f"- {x}")

    if opps:
        st.markdown("#### Mögliche Decision-Support Opportunities")
        for x in (opps if isinstance(opps, list) else [opps])[:10]:
            if x:
                st.write(f"- {x}")

    if uncs:
        st.markdown("#### Unklarheiten")
        for x in (uncs if isinstance(uncs, list) else [uncs])[:8]:
            if x:
                st.write(f"- {x}")

    # --- BOTTOM: Sources (below Unklarheiten) ---
    if sources:
        st.markdown("#### Quellen")
        for s in sources[:8]:
            st.write(f"- {s.get('title','')} — {s.get('url','')}")


# ----------------------------
# Session init
# ----------------------------
if "uv_view" not in st.session_state:
    st.session_state["uv_view"] = "start"  # start | results | brief
if "uv_mode" not in st.session_state:
    st.session_state["uv_mode"] = "specific"  # specific | discover
if "uv_start_step" not in st.session_state:
    st.session_state["uv_start_step"] = "step1"  # step1 | step2    
if "uv_selected_company" not in st.session_state:
    st.session_state["uv_selected_company"] = None
if "results_df" not in st.session_state:
    st.session_state["results_df"] = pd.DataFrame()

# hidden defaults (keine Admin-Optionen sichtbar)
if "uv_prefs" not in st.session_state:
    st.session_state["uv_prefs"] = {
        "decision_goal": "General decision-support (broad)",
        "risk_tolerance": "Medium",
        "prototype_horizon": "2–4 weeks (strict)",
        "detail_level": "Standard",
        "exclude_local_services": True,
    }
if "uv_caches" not in st.session_state:
    st.session_state["uv_caches"] = {"research": True, "decision": True}


# ----------------------------
# UI Shell (centered)
# ----------------------------
st.markdown('<div class="agentiq-wrap">', unsafe_allow_html=True)
st.markdown('<div class="agentiq-shell">', unsafe_allow_html=True)

# Topbar
cL, cM, cR = st.columns([2, 3, 2], vertical_alignment="center")
with cL:
    st.markdown(
        """
        <div class="agentiq-brand">
          <div class="agentiq-dot"></div>
          <div>
            <div>Agentiq AI</div>
            <div class="agentiq-sub">Decision Support Agent (Demo)</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with cR:
    # 1-click jump to admin page (in the multipage demo app)
    st.page_link("pages/99_Admin.py", label="Admin-Modus", icon="🛠️", use_container_width=True)

st.markdown('<div class="agentiq-body">', unsafe_allow_html=True)

# Optional: “Advanced” (versteckt)
#with st.expander("⚙️ Advanced (Demo Settings)", expanded=False):
#    a1, a2 = st.columns(2)
#    with a1:
#        st.session_state["uv_caches"]["research"] = st.checkbox("Use research cache", value=st.session_state["uv_caches"]["research"])
#        st.session_state["uv_caches"]["decision"] = st.checkbox("Use decision cache", value=st.session_state["uv_caches"]["decision"])
#    with a2:
#        st.session_state["uv_prefs"]["risk_tolerance"] = st.selectbox(
#            "Risk tolerance", ["Low", "Medium", "High"],
#            index=["Low", "Medium", "High"].index(st.session_state["uv_prefs"]["risk_tolerance"])
#        )
#        st.session_state["uv_prefs"]["prototype_horizon"] = st.selectbox(
#            "Prototype horizon", ["2–4 weeks (strict)", "4–6 weeks"],
#            index=["2–4 weeks (strict)", "4–6 weeks"].index(st.session_state["uv_prefs"]["prototype_horizon"])
#        )

# ----------------------------
# START
# ----------------------------
if st.session_state["uv_view"] == "start":

    # ---------- STEP 1 (screen) ----------
    if st.session_state.get("uv_start_step", "step1") == "step1":
        st.markdown('<div class="agentiq-step">Step 1</div>', unsafe_allow_html=True)
        st.markdown('<div class="agentiq-title">Wobei kann ich dir helfen?</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="agentiq-hint">Wähle die Suche aus. Danach bekommst du eine kurze Liste – und dann einen Decision-Support-Brief.</div>',
            unsafe_allow_html=True,
        )
        st.write("")

        m1, m2 = st.columns(2)
        with m1:
            st.markdown("###  Ich habe ein konkretes Unternehmen")
            st.markdown("Suche nach Name oder Domain und wähle die richtige Website aus.")
            if st.button("Konkretes Unternehmen", type="primary", use_container_width=True, key="mode_specific"):
                st.session_state["uv_mode"] = "specific"
                st.session_state["uv_start_step"] = "step2"
                st.rerun()

        with m2:
            st.markdown("###  Vorschläge anhand von Parametern")
            st.markdown("Gib Branche/Region an und erhalte passende Company-Vorschläge.")
            if st.button("Vorschläge finden", type="primary",use_container_width=True, key="mode_discover"):
                st.session_state["uv_mode"] = "discover"
                st.session_state["uv_start_step"] = "step2"
                st.rerun()

    # ---------- STEP 2 (screen) ----------
    else:
        # Back button in its own persistent row (back to Step 1)
        back_row = st.columns([1, 5, 1], vertical_alignment="center")
        with back_row[0]:
            if st.button("← Zurück", type="primary", use_container_width=True, key="back_start_step2"):
                st.session_state["uv_start_step"] = "step1"
                st.rerun()

        st.markdown('<div class="agentiq-step">Step 2</div>', unsafe_allow_html=True)

        # ---- Step 2 content depends on mode ----
        if st.session_state["uv_mode"] == "specific":
            st.markdown('<div class="agentiq-title">Welches Unternehmen?</div>', unsafe_allow_html=True)
            q = st.text_input("Company name oder Domain", placeholder="z.B. Linear, Notion...")
            top_n = st.slider("Anzahl Kandidaten", 1, 10, 5, 1)

            run = st.button("Suchen", type="primary", use_container_width=True, key="run_specific")

            if run:
                if not q.strip():
                    st.error("Bitte gib einen Firmennamen oder eine Domain ein.")
                else:
                    with st.spinner("Suche…"):
                        candidates = find_company_by_name(q, max_results=int(top_n))
                        _set_results(candidates)
                        st.session_state["uv_view"] = "results"
                        st.rerun()

        else:
            st.markdown('<div class="agentiq-title">Welche Art von Unternehmen suchst du?</div>', unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                industry = st.text_input("Branche / Domain", placeholder="z.B. logistics, industrial IoT, SaaS")
                keywords = st.text_input("Keywords (optional)", placeholder="z.B. operations, maintenance, ERP, dispatch")
            with c2:
                country = st.text_input("Land", placeholder="z.B. Germany, UK, Netherlands")
                region = st.text_input("Region / Stadt (optional)", placeholder="z.B. Berlin, NRW")
            top_n = st.slider("Anzahl Vorschläge", 5, 20, 10, 1)

            run = st.button("Companies finden", type="primary", use_container_width=True, key="run_discover")
            if run:
                if not industry.strip() and not keywords.strip():
                    st.error("Bitte gib mindestens eine Branche oder Keywords an.")
                else:
                    spec = DiscoverySpec(
                        industry=industry,
                        keywords=keywords,
                        country=country,
                        region_or_city=region,
                        company_size="",
                        exclude_consumer_services=True,
                    )
                    with st.spinner("Discover…"):
                        items = discover_companies(spec, max_results=int(top_n))
                        _set_results(items)
                        st.session_state["uv_view"] = "results"
                        st.rerun()

# ----------------------------
# RESULTS
# ----------------------------
elif st.session_state["uv_view"] == "results":
    # Back button in its own persistent row
    back_row = st.columns([1, 5, 1], vertical_alignment="center")
    with back_row[0]:
        if st.button("← Zurück", type="primary", use_container_width=True, key="back_results"):
            st.session_state["uv_view"] = "start"
            st.session_state["uv_start_step"] = "step1"
            st.rerun()

    # Title row centered (separate from back button)
    st.markdown('<div class="agentiq-step">Step 3</div>', unsafe_allow_html=True)
    st.markdown('<div class="agentiq-title">Wähle das richtige Unternehmen</div>', unsafe_allow_html=True)


    df = st.session_state["results_df"].copy()
    if df.empty:
        st.warning("Keine Ergebnisse. Bitte starte erneut.")
    else:
        top_k = st.slider("Top N anzeigen", 3, 20, min(10, len(df)), 1)

        st.write("")
        for _, row in df.head(int(top_k)).iterrows():
            cname = str(row.get("company_name", "")).strip()
            curl = str(row.get("company_url", "")).strip()
            snippet = str(row.get("snippet", "")).strip()

            fit_state = (st.session_state.get("fit_by_name") or {}).get(cname)
            fit_score = None
            if isinstance(fit_state, dict):
                fit = fit_state.get("fit", {})
                if isinstance(fit, dict) and isinstance(fit.get("fit_score"), (int, float)):
                    fit_score = int(fit["fit_score"])

            badge_text, badge_cls = _fit_badge(fit_score)

            st.markdown('<div class="agentiq-card">', unsafe_allow_html=True)
            cA, cB, cC = st.columns([5, 2, 2], vertical_alignment="center")
            with cA:
                st.markdown(f"**{cname or '(unknown)'}**")
                if curl:
                    st.caption(curl)
                if snippet:
                    st.write(snippet)
                else:
                    st.caption("Kein Snippet verfügbar.")
            with cB:
                st.markdown(f'<div class="agentiq-metric {badge_cls}">Early fit: <b>{badge_text}</b></div>', unsafe_allow_html=True)
            with cC:
                if st.button("Brief öffnen", type="primary", use_container_width=True, key=f"open_{cname}_{curl}"):
                    st.session_state["uv_selected_company"] = {
                        "company_name": cname,
                        "company_url": curl,
                        "snippet": snippet,
                    }
                    st.session_state["uv_view"] = "brief"
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
            st.write("")

# ----------------------------
# BRIEF
# ----------------------------
elif st.session_state["uv_view"] == "brief":
    sel = st.session_state.get("uv_selected_company") or {}
    cname = str(sel.get("company_name", "")).strip()
    curl = str(sel.get("company_url", "")).strip()
    snippet = str(sel.get("snippet", "")).strip()

    # Back button in its own persistent row
    back_row = st.columns([1, 5, 1], vertical_alignment="center")
    with back_row[0]:
        if st.button("← Zurück", type="primary", use_container_width=True, key="back_brief"):
            st.session_state["uv_view"] = "results"
            st.rerun()

    # Title row centered (separate from back button)
    st.markdown('<div class="agentiq-step">Step 4</div>', unsafe_allow_html=True)
    st.markdown('<div class="agentiq-title">Decision-Support Brief</div>', unsafe_allow_html=True)
    st.markdown(f'<div opacity:.85;">{cname} • {curl}</div>', unsafe_allow_html=True)

    #if snippet:
    #    with st.expander("Gefundener Snippet", expanded=False):
    #        st.write(snippet)


    st.write("")
    a1, a2 = st.columns([1, 1])
    with a1:
        run_research = st.button("Research", type="primary", use_container_width=True, key="run_research_uv")
    with a2:
        run_brief = st.button("Brief generieren", type="primary", use_container_width=True, key="run_brief_uv")

    profile_state = (st.session_state.get("profiles_by_name") or {}).get(cname)
    fit_state = (st.session_state.get("fit_by_name") or {}).get(cname)

    if run_research:
        with st.spinner("Research…"):
            profile_state = _ensure_profile(cname, curl, use_cache=st.session_state["uv_caches"]["research"])
            st.success("Research fertig ✅")

    if run_brief:
        if not profile_state:
            with st.spinner("Research (required)…"):
                profile_state = _ensure_profile(cname, curl, use_cache=st.session_state["uv_caches"]["research"])
        with st.spinner("Scoring…"):
            fit_state = _ensure_fit(
                company_name=cname,
                profile_raw=str(profile_state.get("profile_raw", "") or ""),
                preferences=st.session_state["uv_prefs"],
                use_cache=st.session_state["uv_caches"]["decision"],
            )
            st.success("Brief erstellt ✅")

    st.divider()

    left, right = st.columns(2)  # 50/50

    # -------- LEFT: Company profile (pretty, no raw JSON) --------
    with left:
        st.markdown("###  Company Profile")
        if profile_state:
            # Pretty render instead of raw JSON textarea
            _render_company_profile_pretty(profile_state)
        else:
            st.info("Noch kein Research. Klicke **Research**.")

    # -------- RIGHT: Decision-support result (no raw JSON expander) --------
    with right:
        st.markdown("###  Decision-Support Ergebnis")
        if fit_state and isinstance(fit_state, dict):
            fit = fit_state.get("fit", {}) if isinstance(fit_state.get("fit"), dict) else {}
            score = fit.get("fit_score", None)
            if isinstance(score, (int, float)):
                st.metric("Suitability Score", int(score))
            else:
                st.metric("Suitability Score", "—")

            if fit.get("decision_summary"):
                st.markdown("#### Zusammenfassung")
                st.write(fit["decision_summary"])

            if fit.get("recommended_use_case"):
                st.markdown("#### Vorschlag für Prototy")
                st.info(fit["recommended_use_case"])

            why_good = fit.get("why_good_fit", [])
            why_not = fit.get("why_not", [])
            next_q = fit.get("next_questions", [])

            if why_good:
                st.markdown("#### Warum guter fit?")
                for x in (why_good if isinstance(why_good, list) else [why_good])[:6]:
                    if x:
                        st.write(f"- {x}")

            if why_not:
                st.markdown("#### Risiken")
                for x in (why_not if isinstance(why_not, list) else [why_not])[:6]:
                    if x:
                        st.write(f"- {x}")

            if next_q:
                st.markdown("#### Offene Fragen")
                for x in (next_q if isinstance(next_q, list) else [next_q])[:6]:
                    if x:
                        st.write(f"- {x}")
        else:
            st.info("Noch kein Brief. Klicke **Brief generieren**.")

# close shell
st.markdown("</div>", unsafe_allow_html=True)  # agentiq-body
st.markdown("</div>", unsafe_allow_html=True)  # agentiq-shell
st.markdown("</div>", unsafe_allow_html=True)  # agentiq-wrap
