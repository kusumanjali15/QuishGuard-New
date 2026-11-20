"""Stage 12b: the baseline's static routing and decoy rule match docs/STAGE12B_PLAN.md."""

from quishguard.whale_baseline import (static_decision, static_score_at_load, decoy_decision)


def test_static_score_brand_impersonation_at_load():
    # AiTM (brand), password at load, same-origin (no declared cross-site action) -> 70
    s = static_score_at_load("http://127.0.0.1:8005/", "Formosa Demo Bank - Sign in",
                             has_sensitive_field=True, action_origin=None)
    assert s == 70 and static_decision(s) == "block"


def test_static_score_no_sensitive_field_at_load():
    # delayed page at load: "Loading...", no sensitive field -> untrusted only (20) -> uncertain
    s = static_score_at_load("http://127.0.0.1:8003/otp_late_leak.html", "Formosa Demo Bank - Verify",
                             has_sensitive_field=False, action_origin=None)
    assert s == 20 and static_decision(s) == "uncertain"


def test_static_score_no_brand():
    # no-brand page with a password at load, same-origin -> untrusted only (20) -> uncertain
    s = static_score_at_load("http://127.0.0.1:8005/nobrand", "Account verification",
                             has_sensitive_field=True, action_origin=None)
    assert s == 20 and static_decision(s) == "uncertain"


def test_static_declared_cross_site_action():
    # brand + password + a declared cross-site action -> 100 -> block
    s = static_score_at_load("http://127.0.0.1:8003/x", "Formosa Demo Bank - Sign in",
                             has_sensitive_field=True, action_origin="http://127.0.0.1:8002")
    assert s == 100 and static_decision(s) == "block"


def test_static_thresholds():
    assert static_decision(70) == "block"
    assert static_decision(100) == "block"
    assert static_decision(19) == "allow"
    assert static_decision(0) == "allow"
    assert static_decision(20) == "uncertain"
    assert static_decision(50) == "uncertain"


def test_decoy_rule_order():
    # 1. cross-site leak wins even if an auth error is also shown
    assert decoy_decision(submitted=True, decoy_left_cross_site=True, auth_error=True, accepts=False) == "malicious"
    # 2. genuine auth error -> benign (the AiTM / fake-rejection case)
    assert decoy_decision(submitted=True, decoy_left_cross_site=False, auth_error=True, accepts=False) == "benign"
    # 3. accepts (same-origin harvesting) -> malicious
    assert decoy_decision(submitted=True, decoy_left_cross_site=False, auth_error=False, accepts=True) == "malicious"
    # 4. no submit (delayed / unsolvable CAPTCHA) -> benign
    assert decoy_decision(submitted=False, decoy_left_cross_site=False, auth_error=False, accepts=False) == "benign"
