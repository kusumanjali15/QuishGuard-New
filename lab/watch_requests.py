"""Stage 5: run the automated victim and print EVERY request the page makes.

Start the three lab servers first.  Usage:  python lab\\watch_requests.py
"""

import asyncio
from pathlib import Path

from quishguard.netlog import RequestRecord
from quishguard.qr import decode_qr
from quishguard.victim import visit_and_login

QR_IMAGE = Path(__file__).parent / "qr" / "phish.png"
USERNAME = "demo_user_01"
PASSWORD = "Lab-Pass-4821"


async def main() -> None:
    url = decode_qr(QR_IMAGE)
    requests: list[RequestRecord] = []
    await visit_and_login(url, USERNAME, PASSWORD, record=requests)

    print(f"Page opened from QR: {url}\n")
    print(f"{'#':>2}  {'METHOD':6}  {'TYPE':9}  {'DESTINATION':24}  URL / BODY")
    for i, r in enumerate(requests, start=1):
        # Simple text check for now - Stage 6 does this properly.
        flag = "   <-- carries the password" if PASSWORD in (r.url + (r.body or "")) else ""
        print(f"{i:>2}  {r.method:6}  {r.resource_type:9}  {r.destination:24}  {r.url}{flag}")
        if r.body:
            print(f"{'':48}body: {r.body}")


if __name__ == "__main__":
    asyncio.run(main())
