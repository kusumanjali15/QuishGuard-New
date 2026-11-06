"""Stage 12: tests for the load-time stand-in check."""

from quishguard.loadcheck import load_time_check


def test_immediate_fake_bank_is_caught() -> None:
    v = load_time_check("Formosa Demo Bank - Sign in", has_sensitive_field=True,
                        action_origins=["http://127.0.0.1:8002"], page_origin="http://127.0.0.1:8001")
    assert v.decision == "block"


def test_empty_loading_page_is_allowed() -> None:
    # Delayed-OTP page at load: a brand name but NO sensitive field yet.
    v = load_time_check("Formosa Demo Bank - Verify", has_sensitive_field=False,
                        action_origins=[], page_origin="http://127.0.0.1:8003")
    assert v.decision == "allow"


def test_official_bank_is_allowed() -> None:
    v = load_time_check("Formosa Demo Bank - Sign in", has_sensitive_field=True,
                        action_origins=["http://127.0.0.1:8000"], page_origin="http://127.0.0.1:8000")
    assert v.decision == "allow"
