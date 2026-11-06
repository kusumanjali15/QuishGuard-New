"""Stage 13: tests for the URL normalizer (no model download needed)."""

from quishguard.urlmodel import normalize_url_for_model


def test_strips_http_scheme() -> None:
    assert normalize_url_for_model("http://127.0.0.1:8001/") == "127.0.0.1:8001/"


def test_strips_https_scheme() -> None:
    assert normalize_url_for_model("https://example.com/path") == "example.com/path"


def test_leaves_bare_url_unchanged() -> None:
    assert normalize_url_for_model("example.com/") == "example.com/"
