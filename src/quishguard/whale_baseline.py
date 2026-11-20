"""Stage 12b: a WHALE-INSPIRED baseline - NOT a reimplementation of WHALE's 54-feature
model. The thresholds and the decoy decision rule below are the ones PRE-REGISTERED in
docs/STAGE12B_PLAN.md; do not change them to fit results.

- Static stage: score_send's weights applied to what is visible AT LOAD (interim stage,
  to be replaced by the Stage 13 model). Dual thresholds route each page to block / allow /
  the dynamic stage.
- Decoy rule: the pre-registered ordered rule for judging a page after a decoy submit.
"""

from quishguard.netlog import origin_of
from quishguard.rules import OFFICIAL_ORIGINS, TRUSTED_ORIGINS, WEIGHTS, PageInfo, brand_shown

STATIC_BLOCK = 70   # score >= this -> BLOCK (confident malicious; before the user types)
STATIC_ALLOW = 20   # score <  this -> ALLOW and skip the dynamic stage (confident benign)


def static_score_at_load(page_origin: str, title: str, has_sensitive_field: bool,
                         action_origin: str | None) -> int:
    """score_send's weights on load-time-visible info only.

    has_sensitive_field: a password / one-time-code field present at load.
    action_origin: resolved origin of a form action declared at load, or None if there is
                   no form action, or it is empty / '#' / relative (destination unknown).
    """
    po = origin_of(page_origin) if "://" in page_origin else page_origin
    score = 0
    if po not in TRUSTED_ORIGINS:
        score += WEIGHTS["untrusted"]
    brand = brand_shown(PageInfo(po, title))
    # impersonation requires a credential field AT LOAD (same condition as the load-time check)
    if brand and po not in OFFICIAL_ORIGINS.get(brand, set()) and has_sensitive_field:
        score += WEIGHTS["impersonation"]
    # cross_site only when a destination is actually declared at load and it differs
    if action_origin and action_origin != po and action_origin not in TRUSTED_ORIGINS:
        score += WEIGHTS["cross_site"]
    return score


def static_decision(score: int) -> str:
    """Dual-threshold routing: 'block' / 'allow' / 'uncertain' (-> dynamic stage)."""
    if score >= STATIC_BLOCK:
        return "block"
    if score < STATIC_ALLOW:
        return "allow"
    return "uncertain"


def decoy_decision(*, submitted: bool, decoy_left_cross_site: bool,
                   auth_error: bool, accepts: bool) -> str:
    """Pre-registered ordered decoy rule (first match wins). Returns 'malicious'/'benign'.

    1. decoy leaves cross-site        -> malicious
    2. authentication error           -> benign (page rejected the decoy)
    3. page accepts the decoy         -> malicious (advances, no error)
    4. otherwise (incl. no submit)    -> benign
    """
    if decoy_left_cross_site:
        return "malicious"
    if auth_error:
        return "benign"
    if accepts:
        return "malicious"
    return "benign"
