"""Stage 5: tests for origin_of and RequestRecord."""

from quishguard.netlog import RequestRecord, origin_of


def test_origin_keeps_scheme_host_and_port() -> None:
    assert origin_of("http://127.0.0.1:8002/collect?x=1") == "http://127.0.0.1:8002"


def test_different_ports_are_different_origins() -> None:
    assert origin_of("http://127.0.0.1:8000/") != origin_of("http://127.0.0.1:8001/")


def test_origin_is_case_insensitive() -> None:
    assert origin_of("HTTP://Formosa-Demo-Bank.LAB/login") == "http://formosa-demo-bank.lab"


def test_record_destination() -> None:
    rec = RequestRecord("POST", "http://127.0.0.1:8002/collect", "document", "a=1")
    assert rec.destination == "http://127.0.0.1:8002"
