"""Stage 12b: short observed/typed values must not match random requests.

A 1-2 char value like "1" appears in almost any URL, so matching on it would block
everything. MIN_LENGTH (sensitive.py) guards both the matcher (carries_sensitive)
and the observed set (observe_values).
"""

from quishguard.guard import Guard
from quishguard.netlog import RequestRecord
from quishguard.rules import PageInfo, ScanContext
from quishguard.sensitive import MIN_LENGTH, carries_sensitive
from quishguard.sensor import observe_values


def _rec(body: str | None = None, url: str = "http://127.0.0.1:8002/collect") -> RequestRecord:
    return RequestRecord("POST", url, "fetch", body)


def test_short_value_does_not_match():
    # "1" is in the URL, but it is below MIN_LENGTH, so it must not match.
    assert carries_sensitive(_rec(url="http://127.0.0.1:8002/collect?k=1"), ["1"]) is False
    assert carries_sensitive(_rec(body="x=ab"), ["ab"]) is False


def test_long_value_still_matches():
    assert carries_sensitive(_rec(body="linking_code=LINK-7788"), ["LINK-7788"]) is True


def test_observe_values_filters_short():
    guard = Guard(scan=ScanContext(from_qr=True))
    observe_values(guard, ["1", "ab", "abc", "abcd", "LINK-7788", ""])
    # only values with length >= MIN_LENGTH survive
    assert guard.observed == {"abcd", "LINK-7788"}
    assert all(len(v) >= MIN_LENGTH for v in guard.observed)


def test_guard_does_not_block_on_short_observed_value():
    page = PageInfo("http://127.0.0.1:8003/login", "Formosa Demo Bank - Sign in")

    short = Guard(scan=ScanContext(from_qr=True), observed={"1"}, page=page)
    assert short.decide(_rec(body="k=1")) == "continue"          # short -> no match -> allowed

    real = Guard(scan=ScanContext(from_qr=True), observed={"Lab-Pass-4821"}, page=page)
    assert real.decide(_rec(body="password=Lab-Pass-4821")) == "abort"  # real secret -> blocked
