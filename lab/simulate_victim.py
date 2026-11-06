"""Stage 4: an automated victim scans the phishing QR and signs in.

Start the three lab servers first (bank, phish, collector).
Usage:  python lab\\simulate_victim.py          (headless)
        python lab\\simulate_victim.py --show   (watch the browser)
"""

import asyncio
import sys
from pathlib import Path

from quishguard.qr import decode_qr
from quishguard.victim import visit_and_login

LAB = Path(__file__).parent
QR_IMAGE = LAB / "qr" / "phish.png"
ATTACKER_LOG = LAB.parent / "logs" / "attacker.log"

USERNAME = "demo_user_01"    # fake lab credentials only
PASSWORD = "Lab-Pass-4821"


def count_log_entries() -> int:
    """How many leaks the attacker log holds right now."""
    if not ATTACKER_LOG.exists():
        return 0
    return len(ATTACKER_LOG.read_text(encoding="utf-8").splitlines())


async def main() -> None:
    url = decode_qr(QR_IMAGE)
    print(f"1. Scanned QR            -> {url}")

    before = count_log_entries()
    final_url = await visit_and_login(url, USERNAME, PASSWORD, headless="--show" not in sys.argv)
    after = count_log_entries()

    print(f"2. Signed in, ended on   -> {final_url}")
    print(f"3. Attacker log entries  -> {before} before, {after} after")
    print("RESULT: LEAK - password reached the attacker" if after > before else "RESULT: no leak")


if __name__ == "__main__":
    asyncio.run(main())
