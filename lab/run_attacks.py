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

# name, page URL, kind ("attack" must leak without protection; "benign" must never leak)
CASES = [
    ("beacon-on-blur", "http://127.0.0.1:8003/beacon_leak.html", "attack", 0),
    ("beacon benign", "http://127.0.0.1:8003/beacon_benign.html", "benign", 0),
    ("pixel keylogger", "http://127.0.0.1:8003/pixel_leak.html", "attack", 0),
    ("pixel benign", "http://127.0.0.1:8003/pixel_benign.html", "benign", 0),
    ("otp-appears-late", "http://127.0.0.1:8003/otp_late_leak.html", "attack", 3000),
    ("otp-late benign", "http://127.0.0.1:8003/otp_late_benign.html", "benign", 3000),
]
SETTINGS = ["none", "sensor", "network", "both"]


def leaks() -> int:
    return len(ATTACKER_LOG.read_text(encoding="utf-8").splitlines()) if ATTACKER_LOG.exists() else 0


async def run_once(url: str, setting: str, settle_ms: int) -> tuple[int, bool]:
    """Return (new attacker-log entries, whether a layer reported a block)."""
    sensor = Guard(scan=ScanContext(from_qr=True)) if setting in ("sensor", "both") else None
    guard = (Guard(scan=ScanContext(from_qr=True), typed_values=[PASSWORD, OTP])
             if setting in ("network", "both") else None)

    before = leaks()
    await visit_and_interact(url, guard=guard, sensor=sensor, settle_ms=settle_ms)
    await asyncio.sleep(0.4)  # let beacons flush and servers write

    leaked = leaks() - before
    blocked = any("BLOCK" in line or "dropped" in line
                  for g in (sensor, guard) if g for line in g.log)
    return leaked, blocked


async def main() -> None:
    print(f"\n{'ATTACK':16} {'KIND':7} " + " ".join(f"{s:>9}" for s in SETTINGS))
    for name, url, kind, settle_ms in CASES:
        cells = []
        for setting in SETTINGS:
            leaked, blocked = await run_once(url, setting, settle_ms)
            mark = "LEAK" if leaked else ("BLOCK" if blocked else "ok")
            cells.append(f"{mark:>9}")
        print(f"{name:16} {kind:7} " + " ".join(cells))
    print("\nok = nothing reached the attacker;  LEAK = password reached it;  BLOCK = a layer stopped it")


if __name__ == "__main__":
    asyncio.run(main())
