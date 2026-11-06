"""Stage 8: tests for Guard.decide (no browser needed)."""

from quishguard.guard import Guard
from quishguard.netlog import RequestRecord
from quishguard.rules import PageInfo, ScanContext

PASSWORD = "Lab-Pass-4821"
BODY = f"username=demo_user_01&password={PASSWORD}"
BANK = PageInfo("http://127.0.0.1:8000/", "Formosa Demo Bank - Sign in")
PHISH = PageInfo("http://127.0.0.1:8001/", "Formosa Demo Bank - Sign in")


def guard_on(page: PageInfo) -> Guard:
    return Guard(scan=ScanContext(from_qr=True), typed_values=[PASSWORD], page=page)


def test_official_bank_login_is_allowed() -> None:
    g = guard_on(BANK)
    rec = RequestRecord("POST", "http://127.0.0.1:8000/login", "document", BODY)
    assert g.decide(rec) == "continue"
    assert not g.contained


def test_phishing_send_is_blocked_and_page_contained() -> None:
    g = guard_on(PHISH)
    rec = RequestRecord("POST", "http://127.0.0.1:8002/collect", "document", BODY)
    assert g.decide(rec) == "abort"
    assert g.contained


def test_containment_blocks_later_same_origin_requests() -> None:
    g = guard_on(PHISH)
    g.decide(RequestRecord("POST", "http://127.0.0.1:8002/collect", "document", BODY))
    # A harmless-looking request to the page's OWN origin, after the block:
    later = RequestRecord("GET", "http://127.0.0.1:8001/next.js", "script", None)
    assert g.decide(later) == "abort"


def test_harmless_page_load_is_allowed() -> None:
    g = guard_on(PHISH)
    rec = RequestRecord("GET", "http://127.0.0.1:8001/", "document", None)
    assert g.decide(rec) == "continue"   # nothing sensitive, no block yet
