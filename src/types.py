from dataclasses import dataclass, field
from typing import List


@dataclass
class Lead:
    company_name: str
    company_url: str = ""
    notes: str = ""


@dataclass
class SearchSpec:
    """
    Used to prioritize/screen the loaded leads list.
    (Later: can drive automated discovery, but not in this simplified version.)
    """

    exclude_consumer_services: bool = True
    prefer_b2b: bool = True

    # Keyword hints for industry matching (soft)
    industry_keywords: List[str] = field(default_factory=list)

    # Kept for forward-compatibility, but unused in simplified UI.
    agentic_signals: List[str] = field(default_factory=list)

    # Output constraints
    min_score: int = 45
    max_results: int = 30
