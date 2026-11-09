"""Stage 14.2: tests for the detectors (small in-memory frames, no network)."""

import pandas as pd

from quishguard import detectors as d


def _df(rows: list[dict]) -> pd.DataFrame:
    cols = ["has_password_field", "has_html", "input_fields", "input_count", "form_count",
            "external_script_urls", "iframe_srcs", "external_domains", "extracted_text",
            "title", "inline_scripts_total_bytes", "text_length", "http_status",
            "domain", "form_actions"]
    return pd.DataFrame([{c: r.get(c) for c in cols} for r in rows])


def test_password_and_no_inputs() -> None:
    df = _df([{"has_password_field": True, "input_count": 2},
              {"has_password_field": False, "input_count": 0}])
    assert list(d.password_present(df)) == [True, False]
    assert list(d.no_input_fields(df)) == [False, True]


def test_multi_step_identifier_without_password() -> None:
    df = _df([{"has_password_field": False, "input_count": 1,
               "input_fields": [{"type": "email", "name": "email"}]}])
    assert bool(d.multi_step_no_password(df).iloc[0])


def test_captcha_widget_host_and_text() -> None:
    df = _df([{"external_script_urls": ["https://www.google.com/recaptcha/api.js"]},
              {"extracted_text": "Please verify you are human"},
              {"title": "recaptcha", "extracted_text": "welcome"}])  # text marker only on extracted_text
    assert list(d.captcha_widget(df)) == [True, True, False]


def test_cloudflare_interstitial_separate_from_widget() -> None:
    df = _df([{"external_domains": ["challenges.cloudflare.com"]},
              {"extracted_text": "Checking your browser before accessing"}])
    assert list(d.cloudflare_interstitial(df)) == [True, True]
    assert list(d.captcha_widget(df)) == [False, False]   # not counted as a kit gate


def test_non_credential_lure_requires_non_password_input() -> None:
    df = _df([
        {"has_password_field": False, "extracted_text": "Enter your card number and CVV",
         "input_fields": [{"type": "text", "name": "card"}]},                       # lure
        {"has_password_field": False, "extracted_text": "Enter your card number"},    # no input field -> not counted
        {"has_password_field": False, "extracted_text": "輸入您的卡號",
         "input_fields": [{"type": "text", "name": "card"}]},                        # zh-TW card number
    ])
    assert list(d.non_credential_lure(df)) == [True, False, True]


def test_dead_strong_and_weak_split() -> None:
    df = _df([{"http_status": 404, "has_html": True, "text_length": 500, "title": "x"},
              {"http_status": 200, "has_html": False, "text_length": 500, "title": "x"},
              {"http_status": 200, "has_html": True, "text_length": 10, "title": "x"},
              {"http_status": 200, "has_html": True, "text_length": 500, "title": "domain for sale"}])
    assert list(d.dead_strong(df)) == [True, True, False, False]
    assert list(d.dead_weak(df)) == [False, False, True, True]


def test_cross_site_form_action_registrable_domain() -> None:
    df = _df([
        {"domain": "login.bank-example.com", "form_actions": ["https://bank-example.com/do"]},  # same eTLD+1
        {"domain": "bank-example.com", "form_actions": ["https://collector-xyz.net/x"]},        # cross-site
        {"domain": "bank-example.com", "form_actions": ["/login"]},                             # relative -> same
        {"domain": "bank-example.com", "form_actions": ["#"]},                                  # fragment -> same
    ])
    assert list(d.cross_site_form_action(df)) == [False, True, False, False]


def test_brand_mention_whole_word() -> None:
    df = _df([{"title": "Apple ID login"}, {"title": "pineapple recipes"},
              {"extracted_text": "add me on LINE"}, {"extracted_text": "deadline today"}])
    assert list(d.brand_mention(df)) == [True, False, True, False]
