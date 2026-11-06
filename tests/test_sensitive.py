"""Stage 6: tests for carries_sensitive."""

from quishguard.netlog import RequestRecord
from quishguard.sensitive import carries_sensitive

PASSWORD = "Lab-Pass-4821"


def make(method: str, url: str, body: str | None = None, kind: str = "document") -> RequestRecord:
    return RequestRecord(method, url, kind, body)


def test_password_in_form_body() -> None:
    rec = make("POST", "http://127.0.0.1:8002/collect",
               "username=demo_user_01&password=Lab-Pass-4821")
    assert carries_sensitive(rec, [PASSWORD])


def test_password_in_query_string() -> None:
    rec = make("GET", "http://127.0.0.1:8002/collect?password=Lab-Pass-4821")
    assert carries_sensitive(rec, [PASSWORD])


def test_url_encoded_password_is_found() -> None:
    # "Lab Pass@4821" is sent as "Lab+Pass%404821"
    rec = make("POST", "http://127.0.0.1:8002/collect", "password=Lab+Pass%404821")
    assert carries_sensitive(rec, ["Lab Pass@4821"])


def test_password_in_json_body() -> None:
    rec = make("POST", "http://127.0.0.1:8002/api", '{"pw": "Lab-Pass-4821"}', kind="fetch")
    assert carries_sensitive(rec, [PASSWORD])


def test_unrelated_request_is_not_flagged() -> None:
    rec = make("GET", "http://127.0.0.1:8000/")
    assert not carries_sensitive(rec, [PASSWORD])


def test_short_values_are_ignored() -> None:
    # "80" appears in the port number - must not count as a match.
    rec = make("GET", "http://127.0.0.1:8000/")
    assert not carries_sensitive(rec, ["80"])


def test_nothing_typed_means_nothing_carried() -> None:
    rec = make("POST", "http://127.0.0.1:8002/collect", "password=Lab-Pass-4821")
    assert not carries_sensitive(rec, [])
