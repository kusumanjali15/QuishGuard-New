"""Stage 11: run each attack (and its harmless twin) under four settings and
measure what reaches the attacker. Shows WHICH LAYER catches each attack.

Start the lab first:  python lab\\start_lab.py      (now includes port 8003)
Then:                 python lab\\run_attacks.py
"""

import asyncio
from pathlib import Path

from quishguard.guard import Guard
from quishguard.rules import ScanContext
from quishguard.victim import visit_and_interact

LAB = Path(__file__).parent
ATTACKER_LOG = LAB.parent / "logs" / "attacker.log"
PASSWORD, OTP = "Lab-Pass-4821", "123456"   # told to the network-only guard
LINK_CODE = "LINK-7788"                      # a non-credential secret; NOT told to the guard

# name, page URL, kind ("attack" must leak without protection; "benign" must never leak)
CASES = [
    ("beacon-on-blur", "http://127.0.0.1:8003/beacon_leak.html", "attack", 0, None),
    ("beacon benign", "http://127.0.0.1:8003/beacon_benign.html", "benign", 0, None),
    ("pixel keylogger", "http://127.0.0.1:8003/pixel_leak.html", "attack", 0, None),
    ("pixel benign", "http://127.0.0.1:8003/pixel_benign.html", "benign", 0, None),
    ("otp-appears-late", "http://127.0.0.1:8003/otp_late_leak.html", "attack", 3000, None),
    ("otp-late benign", "http://127.0.0.1:8003/otp_late_benign.html", "benign", 3000, None),
    ("captcha+websocket", "http://127.0.0.1:8003/captcha_ws_leak.html", "attack", 0, "#captcha"),
    ("captcha benign", "http://127.0.0.1:8003/captcha_ws_benign.html", "benign", 0, "#captcha"),
    ("link-code scam", "http://127.0.0.1:8003/link_scam_leak.html", "attack", 0, None),
    ("link-code benign", "http://127.0.0.1:8003/link_scam_benign.html", "benign", 0, None),
]
SETTINGS = ["none", "sensor", "network", "both"]


def log_lines() -> list[str]:
    return ATTACKER_LOG.read_text(encoding="utf-8").splitlines() if ATTACKER_LOG.exists() else []


def count_secret_leaks(new_lines: list[str]) -> int:
    """A leak = an attacker-log line that actually contains a sensitive value."""
    return sum(1 for ln in new_lines if any(s in ln for s in (PASSWORD, OTP, LINK_CODE)))


async def run_once(url: str, setting: str, settle_ms: int, pre_click: str | None) -> tuple[int, bool]:
    """Return (new attacker-log entries, whether a layer reported a block)."""
    sensor = Guard(scan=ScanContext(from_qr=True)) if setting in ("sensor", "both") else None
    guard = (Guard(scan=ScanContext(from_qr=True), typed_values=[PASSWORD, OTP])
             if setting in ("network", "both") else None)

    before = log_lines()
    await visit_and_interact(url, guard=guard, sensor=sensor, settle_ms=settle_ms, pre_click=pre_click)
    await asyncio.sleep(0.5)  # let beacons/ws flush and servers write

    leaked = count_secret_leaks(log_lines()[len(before):])
    blocked = any("BLOCK" in line or "dropped" in line
                  for g in (sensor, guard) if g for line in g.log)
    return leaked, blocked


async def main() -> None:
    print(f"\n{'ATTACK':16} {'KIND':7} " + " ".join(f"{s:>9}" for s in SETTINGS))
    for name, url, kind, settle_ms, pre_click in CASES:
        cells = []
        for setting in SETTINGS:
            leaked, blocked = await run_once(url, setting, settle_ms, pre_click)
            mark = "LEAK" if leaked else ("BLOCK" if blocked else "ok")
            cells.append(f"{mark:>9}")
        print(f"{name:16} {kind:7} " + " ".join(cells))
    print("\nok = nothing reached the attacker;  LEAK = password reached it;  BLOCK = a layer stopped it")


if __name__ == "__main__":
    asyncio.run(main())
