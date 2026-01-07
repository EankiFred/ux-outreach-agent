# pages/99_Admin.py
# Admin-UI (verbatim aus app.py) – nur OHNE st.set_page_config(...)!

import streamlit as st
import pandas as pd

from src.io import load_leads_csv
from src.research import build_company_profile
from src.fit import score_company_fit
from src.discovery import DiscoverySpec, find_company_by_name, discover_companies


# ----------------------------
# Helpers
# ----------------------------
def _fit_badge(score: int | None) -> str:
    if score is None:
        return "—"
    if score >= 75:
        return "Strong"
    if score >= 55:
        return "Promising"
    if score >= 40:
        return "Maybe"
    return "Weak"


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


# ----------------------------
# Session init
# ----------------------------
if "view" not in st.session_state:
    st.session_state["view"] = "start"  # start | results | brief
if "mode" not in st.session_state:
    st.session_state["mode"] = "specific"  # specific | discover
if "selected_company" not in st.session_state:
    st.session_state["selected_company"] = None
if "results_df" not in st.session_state:
    st.session_state["results_df"] = pd.DataFrame()


# ----------------------------
# Page
# ----------------------------
st.title("Agentiq AI — Decision Support Agent (Admin)")
st.caption("Admin view (unchanged).")

# ----------------------------
# Sidebar: computation + fallback CSV
# ----------------------------
st.sidebar.header("Computation")
use_research_cache = st.sidebar.checkbox("Use research cache", value=True)
use_decision_cache = st.sidebar.checkbox("Use decision cache", value=True)

st.sidebar.divider()
st.sidebar.header("Fit preferences (MVP)")
decision_goal = st.sidebar.text_input("Decision goal", value="General decision-support (broad)")
risk_tolerance = st.sidebar.selectbox("Risk tolerance", ["Low", "Medium", "High"], index=1)
prototype_horizon = st.sidebar.selectbox("Prototype horizon", ["2–4 weeks (strict)", "4–6 weeks"], index=0)
detail_level = st.sidebar.selectbox("Detail level", ["Standard", "More detailed"], index=0)

exclude_local_services = st.sidebar.checkbox("Exclude local consumer services", value=True)

fit_preferences = {
    "decision_goal": decision_goal,
    "risk_tolerance": risk_tolerance,
    "prototype_horizon": prototype_horizon,
    "detail_level": detail_level,
    "exclude_local_services": exclude_local_services,
}

st.sidebar.divider()
st.sidebar.header("CSV fallback (optional)")
csv_path = st.sidebar.text_input("Companies CSV path", value="data/leads.csv")
csv_top_k = st.sidebar.slider("CSV: show top N", 3, 30, 10, 1)

if st.sidebar.button("Load CSV into results"):
    try:
        leads = load_leads_csv(csv_path)
        df = pd.DataFrame([l.__dict__ for l in leads])
        if "notes" not in df.columns:
            df["notes"] = ""
        items = []
        for _, r in df.head(int(csv_top_k)).iterrows():
            items.append({
                "company_name": str(r.get("company_name", "")),
                "company_url": str(r.get("company_url", "")),
                "snippet": str(r.get("notes", "")),
                "source": "csv",
            })
        _set_results(items)
        st.session_state["view"] = "results"
        st.success("Loaded CSV candidates into results ✅")
        st.rerun()
    except Exception as e:
        st.sidebar.error(f"CSV load failed: {e}")


# ----------------------------
# START: choose mode + input
# ----------------------------
if st.session_state["view"] == "start":
    st.subheader("1) Choose your search mode")

    st.session_state["mode"] = st.radio(
        "Mode",
        options=["specific", "discover"],
        format_func=lambda x: "I have a specific company in mind" if x == "specific" else "Suggest companies from parameters",
        horizontal=True,
    )

    st.divider()

    if st.session_state["mode"] == "specific":
        st.subheader("2) Search a specific company")
        company_query = st.text_input(
            "Company name or domain",
            placeholder="e.g. Linear, Notion, seba-hydrometrie.com",
        )
        top_n = st.slider("How many candidates to show", 1, 10, 5, 1)

        colA, colB = st.columns([1, 2])
        with colA:
            run = st.button("Search", use_container_width=True)
        with colB:
            st.caption("We do a lightweight web search and show the best candidate websites.")

        if run:
            if not company_query.strip():
                st.error("Please enter a company name or domain.")
            else:
                with st.spinner("Searching the web…"):
                    try:
                        candidates = find_company_by_name(company_query, max_results=int(top_n))
                        _set_results(candidates)
                        st.session_state["view"] = "results"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Search failed: {e}")

    else:
        st.subheader("2) Discover companies from parameters")
        c1, c2, c3 = st.columns(3)
        with c1:
            industry = st.text_input("Industry / domain", placeholder="e.g. logistics, industrial IoT, SaaS")
            company_size = st.selectbox(
                "Company size (rough)",
                ["", "1-10", "11-50", "51-200", "201-1000", "1000+"],
                index=0,
            )
        with c2:
            country = st.text_input("Country", placeholder="e.g. Germany, UK, Netherlands")
            region = st.text_input("Region / city (optional)", placeholder="e.g. Berlin, NRW")
        with c3:
            keywords = st.text_input("Keywords (optional)", placeholder="e.g. operations, maintenance, ERP, dispatch")
            top_n = st.slider("How many suggestions", 5, 20, 10, 1)

        colA, colB = st.columns([1, 2])
        with colA:
            run = st.button("Find companies", use_container_width=True)
        with colB:
            st.caption("We do a lightweight web search and return a short list of candidate company websites.")

        if run:
            if not industry.strip() and not keywords.strip():
                st.error("Please provide at least an industry or some keywords.")
            else:
                spec = DiscoverySpec(
                    industry=industry,
                    keywords=keywords,
                    country=country,
                    region_or_city=region,
                    company_size=company_size,
                    exclude_consumer_services=exclude_local_services,
                )
                with st.spinner("Discovering companies…"):
                    try:
                        items = discover_companies(spec, max_results=int(top_n))
                        _set_results(items)
                        st.session_state["view"] = "results"
                        st.rerun()
                    except Exception as e:
                        st.error(f"Discovery failed: {e}")

    st.stop()


# ----------------------------
# RESULTS: Top 10 cards
# ----------------------------
if st.session_state["view"] == "results":
    st.subheader("3) Results (pick one company)")

    df = st.session_state["results_df"].copy()
    if df.empty:
        st.warning("No results available. Go back and search again.")
        if st.button("← Back"):
            st.session_state["view"] = "start"
            st.rerun()
        st.stop()

    top_k = st.slider("Show top N results", 3, 20, min(10, len(df)), 1)

    if st.button("← Back to search"):
        st.session_state["view"] = "start"
        st.rerun()

    st.divider()

    for _, row in df.head(int(top_k)).iterrows():
        cname = str(row.get("company_name", "")).strip()
        curl = str(row.get("company_url", "")).strip()
        snippet = str(row.get("snippet", "")).strip()

        # early fit (only if already computed before)
        fit_state = (st.session_state.get("fit_by_name") or {}).get(cname)
        fit_score = None
        if isinstance(fit_state, dict):
            fit = fit_state.get("fit", {})
            if isinstance(fit, dict) and isinstance(fit.get("fit_score"), (int, float)):
                fit_score = int(fit["fit_score"])

        with st.container(border=True):
            cols = st.columns([3, 1, 1])
            with cols[0]:
                st.markdown(f"**{cname or '(unknown)'}**")
                if curl:
                    st.caption(curl)
            with cols[1]:
                st.metric("Early fit", _fit_badge(fit_score))
            with cols[2]:
                if st.button("Open brief", key=f"open_{cname}_{curl}", use_container_width=True):
                    st.session_state["selected_company"] = {
                        "company_name": cname,
                        "company_url": curl,
                        "snippet": snippet,
                    }
                    st.session_state["view"] = "brief"
                    st.rerun()

            if snippet:
                st.write(snippet)
            else:
                st.caption("No snippet available.")

    st.stop()


# ----------------------------
# BRIEF: Research + decision-support
# ----------------------------
if st.session_state["view"] == "brief":
    sel = st.session_state.get("selected_company") or {}
    cname = str(sel.get("company_name", "")).strip()
    curl = str(sel.get("company_url", "")).strip()
    snippet = str(sel.get("snippet", "")).strip()

    if not cname or not curl:
        st.warning("Selected company is missing name or URL. Please pick another result.")
        if st.button("← Back to results"):
            st.session_state["view"] = "results"
            st.rerun()
        st.stop()

    head = st.columns([1, 3, 1])
    with head[0]:
        if st.button("← Back to results", use_container_width=True):
            st.session_state["view"] = "results"
            st.rerun()
    with head[1]:
        st.subheader(f"Decision-support brief — {cname}")
        st.caption(curl)
    with head[2]:
        if st.button("Reset session cache", use_container_width=True):
            if "profiles_by_name" in st.session_state:
                st.session_state["profiles_by_name"].pop(cname, None)
            if "fit_by_name" in st.session_state:
                st.session_state["fit_by_name"].pop(cname, None)
            st.success("Cleared session cache for this company.")
            st.rerun()

    if snippet:
        with st.expander("Result snippet", expanded=False):
            st.write(snippet)

    st.divider()

    action_cols = st.columns([1, 1, 2])
    with action_cols[0]:
        run_research = st.button("Run research", use_container_width=True)
    with action_cols[1]:
        run_brief = st.button("Generate brief", use_container_width=True)
    with action_cols[2]:
        st.caption("Research → grounded profile. Brief → suitability score + prototype suggestion + open questions.")

    profile_state = (st.session_state.get("profiles_by_name") or {}).get(cname)
    fit_state = (st.session_state.get("fit_by_name") or {}).get(cname)

    if run_research:
        with st.spinner("Fetching pages & building profile…"):
            try:
                profile_state = _ensure_profile(cname, curl, use_cache=use_research_cache)
                st.success("Research complete ✅")
            except Exception as e:
                st.error(f"Research failed: {e}")

    if run_brief:
        # ensure profile exists
        if not profile_state:
            with st.spinner("Research first (required)…"):
                try:
                    profile_state = _ensure_profile(cname, curl, use_cache=use_research_cache)
                except Exception as e:
                    st.error(f"Research failed: {e}")
                    profile_state = None

        if profile_state:
            with st.spinner("Scoring decision suitability…"):
                try:
                    fit_state = _ensure_fit(
                        company_name=cname,
                        profile_raw=str(profile_state.get("profile_raw", "") or ""),
                        preferences=fit_preferences,
                        use_cache=use_decision_cache,
                    )
                    st.success("Decision brief generated ✅")
                except Exception as e:
                    st.error(f"Decision scoring failed: {e}")

    st.divider()

    st.subheader("Company profile (grounded in website)")
    if profile_state:
        st.caption("Research cache: " + ("✅ Yes" if profile_state.get("from_cache") else "❌ No"))
        sources = profile_state.get("sources", []) or []
        if sources:
            st.write("**Sources used**")
            for s in sources[:8]:
                st.write(f"- {s.get('title','')} — {s.get('url','')}")
        with st.expander("Raw profile output (debug)", expanded=False):
            st.text_area("Profile (raw)", value=str(profile_state.get("profile_raw", "") or ""), height=260)
    else:
        st.info("No research yet. Click **Run research**.")

    st.divider()

    st.subheader("Decision-support brief")
    if fit_state:
        st.caption("Decision cache: " + ("✅ Yes" if fit_state.get("from_cache") else "❌ No"))

        fit = fit_state.get("fit", {}) if isinstance(fit_state, dict) else {}
        score = fit.get("fit_score") if isinstance(fit, dict) else None

        if isinstance(score, (int, float)):
            st.metric("Decision suitability score", int(score))
        else:
            st.metric("Decision suitability score", "—")

        decision_summary = fit.get("decision_summary", "")
        recommended = fit.get("recommended_use_case", "")
        why_good = fit.get("why_good_fit", [])
        why_not = fit.get("why_not", [])
        next_q = fit.get("next_questions", [])

        if decision_summary:
            st.write("**Decision summary**")
            st.write(decision_summary)

        if recommended:
            st.write("**Suggested prototype**")
            st.info(recommended)

        if why_good:
            st.write("**Why this could work**")
            for x in (why_good if isinstance(why_good, list) else [why_good])[:7]:
                st.write(f"- {x}")

        if why_not:
            st.write("**Risks / concerns**")
            for x in (why_not if isinstance(why_not, list) else [why_not])[:7]:
                st.write(f"- {x}")

        if next_q:
            st.write("**Open questions**")
            for x in (next_q if isinstance(next_q, list) else [next_q])[:7]:
                st.write(f"- {x}")

        with st.expander("Raw decision JSON (debug)", expanded=False):
            st.text_area("Decision output (raw)", value=str(fit_state.get("fit_raw", "") or ""), height=260)
    else:
        st.info("No decision brief yet. Click **Generate brief**.")
