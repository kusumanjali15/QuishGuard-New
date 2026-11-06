"""Stage 10: tests for judge_held_send (the Python half of the sensor)."""

from quishguard.guard import Guard
from quishguard.rules import ScanContext
from quishguard.sensor import judge_held_send

PASSWORD = "Lab-Pass-4821"


def send(page_url: str, url: str, channel: str = "form", body: str | None = None) -> dict:
    return {"channel": channel, "method": "POST", "url": url, "body": body,
            "pageUrl": page_url, "title": "Formosa Demo Bank - Sign in", "typed": [PASSWORD]}


def test_phishing_form_send_is_dropped() -> None:
    g = Guard(scan=ScanContext(from_qr=True))
    s = send("http://127.0.0.1:8001/", "http://127.0.0.1:8002/collect",
             body=f"username=demo_user_01&password={PASSWORD}")
    assert judge_held_send(g, s) == "block"
    assert g.contained


def test_official_bank_form_send_is_released() -> None:
    g = Guard(scan=ScanContext(from_qr=True))
    s = send("http://127.0.0.1:8000/", "http://127.0.0.1:8000/login",
             body=f"username=demo_user_01&password={PASSWORD}")
    assert judge_held_send(g, s) == "allow"


def test_typed_values_come_from_the_page() -> None:
    g = Guard(scan=ScanContext(from_qr=True))   # note: no typed_values given
    judge_held_send(g, send("http://127.0.0.1:8001/", "http://127.0.0.1:8002/x", "fetch", PASSWORD))
    assert g.typed_values == [PASSWORD]


def test_held_send_without_sensitive_data_is_released() -> None:
    g = Guard(scan=ScanContext(from_qr=True))
    s = send("http://127.0.0.1:8001/", "http://127.0.0.1:8001/stats", "beacon", "clicks=3")
    assert judge_held_send(g, s) == "allow"
