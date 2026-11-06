"""Stage 8: run the automated victim WITH the guard, on both lab QR codes.

Start the three lab servers first.  Usage:  python lab\\protect_victim.py
"""

import asyncio
from pathlib import Path

from quishguard.guard import Guard
from quishguard.qr import decode_qr
from quishguard.rules import ScanContext
from quishguard.victim import visit_and_login

LAB = Path(__file__).parent
ATTACKER_LOG = LAB.parent / "logs" / "attacker.log"
USERNAME, PASSWORD = "demo_user_01", "Lab-Pass-4821"


def count_log_entries() -> int:
    if not ATTACKER_LOG.exists():
        return 0
    return len(ATTACKER_LOG.read_text(encoding="utf-8").splitlines())


async def run(qr_name: str) -> None:
    url = decode_qr(LAB / "qr" / f"{qr_name}.png")
    guard = Guard(scan=ScanContext(from_qr=True), typed_values=[PASSWORD])

    before = count_log_entries()
    final_url = await visit_and_login(url, USERNAME, PASSWORD, guard=guard)
    leaked = count_log_entries() - before

    print(f"\n=== {qr_name}.png -> {url}")
    for line in guard.log:
        print(f"  {line}")
    print(f"  ended on: {final_url}")
    print(f"  new attacker-log entries: {leaked}  ->  {'LEAK' if leaked else 'no leak'}")


async def main() -> None:
    await run("bank")    # must still work
    await run("phish")   # must leak nothing


if __name__ == "__main__":
    asyncio.run(main())
