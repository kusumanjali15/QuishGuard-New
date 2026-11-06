"""Stage 9: scenarios and pass/fail rules for the experiment runner."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Scenario:
    name: str
    qr_file: str   # file name in lab/qr/
    kind: str      # "attack" or "legit"


SCENARIOS = [
    Scenario("official bank login", "bank.png", "legit"),
    Scenario("phishing -> collector", "phish.png", "attack"),
]


def evaluate(kind: str, protected: bool, leaked: int, bank_logins: int) -> tuple[bool, str]:
    """Decide if one run passed, from what the SERVERS measured."""
    if kind == "legit":
        if leaked == 0 and bank_logins >= 1:
            return True, "login works"
        return False, "legit login broken (false block?)" if bank_logins == 0 else "leak on legit site?!"

    if not protected:  # attack baseline: the attack must really work
        if leaked > 0:
            return True, "attack works (baseline)"
        return False, "attack did not leak - scenario broken"

    if leaked == 0:
        return True, "blocked, nothing leaked"
    return False, "LEAKED despite protection"
