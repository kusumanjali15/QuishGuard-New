"""Stage 7: tests for score_send. Lab origins: bank :8000, phish :8001,
collector :8002, Bean Corner Cafe (unknown shop) :8003."""

from quishguard.rules import PageInfo, ScanContext, score_send

QR = ScanContext(from_qr=True)


def test_official_bank_is_allowed() -> None:
    page = PageInfo("http://127.0.0.1:8000/", "Formosa Demo Bank - Sign in")
    v = score_send(page, "http://127.0.0.1:8000/login", QR)
    assert v.decision == "allow"
    assert v.score == 0 and v.reasons == []


def test_fake_bank_sending_to_collector_is_blocked() -> None:
    page = PageInfo("http://127.0.0.1:8001/", "Formosa Demo Bank - Sign in")
    v = score_send(page, "http://127.0.0.1:8002/collect", QR)
    assert v.decision == "block"
    assert any("Formosa Demo Bank" in r for r in v.reasons)   # explains WHY
    assert any("another site" in r for r in v.reasons)


def test_fake_bank_sending_to_itself_is_still_blocked() -> None:
    # Same-origin theft (kit posts to its own /login) - the Stage 1 lesson.
    page = PageInfo("http://127.0.0.1:8001/", "Formosa Demo Bank - Sign in")
    v = score_send(page, "http://127.0.0.1:8001/login", QR)
    assert v.decision == "block"


def test_unknown_shop_signup_is_allowed() -> None:
    page = PageInfo("http://127.0.0.1:8003/join", "Bean Corner Cafe - Loyalty sign-up")
    v = score_send(page, "http://127.0.0.1:8003/join",
                   ScanContext(from_qr=True, expected_brand="Bean Corner Cafe"))
    assert v.decision == "allow"
    assert v.score == 20   # only "untrusted site" fires


def test_scan_context_mismatch_adds_a_reason() -> None:
    # QR on a cafe table leads to a "bank" login page.
    page = PageInfo("http://127.0.0.1:8001/", "Formosa Demo Bank - Sign in")
    v = score_send(page, "http://127.0.0.1:8001/login",
                   ScanContext(from_qr=True, expected_brand="Bean Corner Cafe"))
    assert v.decision == "block"
    assert any("Bean Corner Cafe" in r for r in v.reasons)
