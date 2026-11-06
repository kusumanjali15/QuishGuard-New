"""Stage 12: a LOAD-TIME STAND-IN check (not WHALE).

Inspects a page ONCE, right after load, using only what a cheap pre-release
checker could see then: the title (brand), whether a sensitive field is already
present, and where any form action points. It cannot see anything the page does
later or in response to the user - that blind spot is the whole point.
"""

from dataclasses import dataclass, field

from quishguard.netlog import origin_of
from quishguard.rules import OFFICIAL_ORIGINS, TRUSTED_ORIGINS


@dataclass
class Verdict:
    decision: str              # "allow" or "block"
    reasons: list[str] = field(default_factory=list)


def _brand_in(title: str) -> str | None:
    for brand in OFFICIAL_ORIGINS:
        if brand.lower() in title.lower():
            return brand
    return None


def load_time_check(
    title: str,
    has_sensitive_field: bool,
    action_origins: list[str],
    page_origin: str,
) -> Verdict:
    """Judge a page from its load-time snapshot only."""
    reasons: list[str] = []
    page_origin = origin_of(page_origin + "/") if "://" in page_origin else page_origin

    brand = _brand_in(title)
    impersonates = bool(brand) and page_origin not in OFFICIAL_ORIGINS.get(brand, set())
    # A load-time checker can only act on what's visible NOW: a brand + a way to
    # submit credentials right here. No sensitive field visible yet -> nothing to flag.
    if impersonates and has_sensitive_field:
        reasons.append(f"page shows '{brand}' off its official site, with a credential field at load")
    if has_sensitive_field and any(o not in TRUSTED_ORIGINS and o != page_origin for o in action_origins):
        reasons.append("a form at load posts credentials to another site")

    return Verdict("block" if reasons else "allow", reasons)
