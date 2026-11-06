"""Stage 7: explainable rules that score a sensitive send.

These weights are hand-picked guesses - a BASELINE, not a measured result.
"""

from dataclasses import dataclass, field

from quishguard.netlog import origin_of

# Fictional brands we protect, and the ONLY origins allowed to show them.
OFFICIAL_ORIGINS: dict[str, set[str]] = {
    "Formosa Demo Bank": {"http://127.0.0.1:8000"},
    "ChatLink": {"http://127.0.0.1:8010"},
}
TRUSTED_ORIGINS: set[str] = set().union(*OFFICIAL_ORIGINS.values())

WEIGHTS = {"untrusted": 20, "impersonation": 50, "cross_site": 30, "scan_mismatch": 30}
BLOCK_THRESHOLD = 60


@dataclass(frozen=True)
class PageInfo:
    """What we know about the page that wants to send data."""
    url: str
    title: str  # visible brand text, e.g. the page <title>


@dataclass(frozen=True)
class ScanContext:
    """How the user got here."""
    from_qr: bool
    expected_brand: str | None = None  # e.g. QR printed on a Bean Corner Cafe table


@dataclass
class Verdict:
    decision: str                       # "allow" or "block"
    score: int
    reasons: list[str] = field(default_factory=list)


def brand_shown(page: PageInfo) -> str | None:
    """Which protected brand (if any) the page presents itself as."""
    for brand in OFFICIAL_ORIGINS:
        if brand.lower() in page.title.lower():
            return brand
    return None


def score_send(page: PageInfo, destination: str, scan: ScanContext) -> Verdict:
    """Score a send of typed sensitive data from `page` to `destination`."""
    page_origin = origin_of(page.url)
    dest_origin = origin_of(destination)
    score = 0
    reasons: list[str] = []

    def fire(rule: str, reason: str) -> None:
        nonlocal score
        score += WEIGHTS[rule]
        reasons.append(f"+{WEIGHTS[rule]} {reason}")

    if page_origin not in TRUSTED_ORIGINS:
        fire("untrusted", f"page {page_origin} is not a known official site")

    brand = brand_shown(page)
    if brand and page_origin not in OFFICIAL_ORIGINS[brand]:
        fire("impersonation", f"page shows '{brand}' but is not on its official site")

    if dest_origin != page_origin:
        fire("cross_site", f"sensitive data goes to another site: {dest_origin}")

    if (scan.from_qr and scan.expected_brand
            and scan.expected_brand.lower() not in page.title.lower()):
        fire("scan_mismatch",
             f"QR was scanned at '{scan.expected_brand}' but the page is '{page.title}'")

    decision = "block" if score >= BLOCK_THRESHOLD else "allow"
    return Verdict(decision, score, reasons)
