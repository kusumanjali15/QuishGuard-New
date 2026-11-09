"""Stage 14: tests for dedup keys and the html parser (no network needed)."""

import pandas as pd

from quishguard.snapshots import (dedup, normalized_html_hash, parse_inputs,
                                   structural_key)


def test_hash_ignores_whitespace_and_case() -> None:
    assert normalized_html_hash("<a>  Hi </a>") == normalized_html_hash("<a>\n\tHi\n</a>")


def test_hash_empty_is_blank() -> None:
    assert normalized_html_hash(None) == "" and normalized_html_hash("") == ""


def test_hash_differs_on_real_content() -> None:
    assert normalized_html_hash("<p>login</p>") != normalized_html_hash("<p>pay</p>")


def test_exact_dedup_keeps_one_per_identical_page() -> None:
    df = pd.DataFrame({"id": ["a", "b", "c"],
                       "html": ["<p>Hi</p>", "<P>hi</P>", "<p>different</p>"]})
    assert list(dedup(df, "exact")["id"]) == ["a", "c"]


def test_structural_key_merges_same_layout_different_tokens() -> None:
    # Same kit, two victims: different domain/token, identical structure.
    a = {"title": "Login", "input_fields": [{"type": "text", "name": "user"},
                                            {"type": "password", "name": "pass"}],
         "input_count": 2, "form_count": 1}
    b = {"title": "Login", "input_fields": [{"type": "password", "name": "pass"},
                                            {"type": "text", "name": "user"}],
         "input_count": 2, "form_count": 1}
    assert structural_key(a) == structural_key(b)


def test_structural_key_differs_on_structure() -> None:
    a = {"title": "Login", "input_fields": [{"type": "password", "name": "pass"}],
         "input_count": 1, "form_count": 1}
    b = {"title": "Pay", "input_fields": [{"type": "text", "name": "card"}],
         "input_count": 1, "form_count": 1}
    assert structural_key(a) != structural_key(b)


def test_parse_inputs_counts_and_finds_password() -> None:
    html = '<form><input type="text" name="u"><input type="password" name="p"></form>'
    assert parse_inputs(html) == (2, True)


def test_parse_inputs_no_password() -> None:
    assert parse_inputs('<input type="text"><input name="code">') == (2, False)
