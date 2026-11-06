"""Stage 9: tests for evaluate()."""

from quishguard.experiment import evaluate


def test_legit_login_passes_when_bank_receives_it() -> None:
    assert evaluate("legit", protected=True, leaked=0, bank_logins=1)[0]


def test_legit_login_fails_if_blocked() -> None:
    ok, note = evaluate("legit", protected=True, leaked=0, bank_logins=0)
    assert not ok and "false block" in note


def test_attack_baseline_must_leak() -> None:
    assert evaluate("attack", protected=False, leaked=1, bank_logins=0)[0]
    assert not evaluate("attack", protected=False, leaked=0, bank_logins=0)[0]


def test_protected_attack_passes_only_without_leak() -> None:
    assert evaluate("attack", protected=True, leaked=0, bank_logins=0)[0]
    assert not evaluate("attack", protected=True, leaked=1, bank_logins=0)[0]
