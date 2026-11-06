"""Stage 1: tests for parse_form_body."""

from quishguard.forms import parse_form_body


def test_simple_login_body() -> None:
    body = "username=demo_user_01&password=Lab-Pass-4821"
    assert parse_form_body(body) == {
        "username": "demo_user_01",
        "password": "Lab-Pass-4821",
    }


def test_encoded_characters_are_decoded() -> None:
    # %40 is "@", "+" is a space
    body = "username=demo%40lab.test&note=hello+world"
    assert parse_form_body(body) == {"username": "demo@lab.test", "note": "hello world"}


def test_empty_field_is_kept() -> None:
    # The user left the password box empty: the field is still sent.
    body = "username=demo_user_01&password="
    assert parse_form_body(body) == {"username": "demo_user_01", "password": ""}


def test_empty_body() -> None:
    assert parse_form_body("") == {}
