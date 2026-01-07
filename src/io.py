import pandas as pd
from .types import Lead


def load_leads_csv(path: str) -> list[Lead]:
    df = pd.read_csv(path).fillna("")
    leads: list[Lead] = []

    for _, row in df.iterrows():
        leads.append(
            Lead(
                company_name=str(row.get("company_name", "")).strip(),
                company_url=str(row.get("company_url", "")).strip(),
                notes=str(row.get("notes", "")).strip(),
            )
        )

    # Deduplicate by (name + url)
    seen = set()
    unique: list[Lead] = []
    for l in leads:
        key = (l.company_name.lower(), l.company_url.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(l)

    return unique
