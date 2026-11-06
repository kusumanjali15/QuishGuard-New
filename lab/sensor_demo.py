"""Stage 10: run both lab QR codes with ONLY the in-page sensor (no network guard).

Start the three lab servers first.  Usage:  python lab\\sensor_demo.py
"""

import asyncio
from pathlib import Path

from quishguard.guard import Guard
from quishguard.qr import decode_qr
from quishguard.rules import ScanContext
from quishguard.victim import visit_and_login

LAB = Path(__file__).parent
ATTACKER_LOG = LAB.parent / "logs" / "attacker.log"


def count_log_entries() -> int:
    return len(ATTACKER_LOG.read_text(encoding="utf-8").splitlines()) if ATTACKER_LOG.exists() else 0


async def run(qr_name: str) -> None:
    url = decode_qr(LAB / "qr" / f"{qr_name}.png")
    sensor = Guard(scan=ScanContext(from_qr=True))  # no typed_values: the sensor observes them
    before = count_log_entries()
    final_url = await visit_and_login(url, "demo_user_01", "Lab-Pass-4821", sensor=sensor)
    leaked = count_log_entries() - before

    print(f"\n=== {qr_name}.png -> {url}")
    for line in sensor.log:
        print(f"  {line}")
    print(f"  ended on: {final_url}")
    print(f"  new attacker-log entries: {leaked}  ->  {'LEAK' if leaked else 'no leak'}")


async def main() -> None:
    await run("bank")
    await run("phish")


if __name__ == "__main__":
    asyncio.run(main())
