"""Stage 11: a WebSocket attacker sink (lab, 127.0.0.1:8004).

Logs every message it receives to logs/attacker.log. Used to show that a login
sent over a WebSocket message is not seen by either QuishGuard layer today.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

import websockets

from quishguard.leaklog import append_log_entry

HOST, PORT = "127.0.0.1", 8004
VERBOSE = False  # set True for the per-message leak prints
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "attacker.log"


async def handle(websocket) -> None:
    try:
        async for message in websocket:
            append_log_entry(LOG_PATH, {
                "time": datetime.now().isoformat(timespec="seconds"),
                "server": "ws-collector",
                "channel": "websocket",
                "fields": {"message": message},
            })
            if VERBOSE:
                print(f"[ws-collector] LEAK logged (websocket): {message}")
    except Exception:
        pass  # the lab browser closed the socket abruptly - not an error


async def main() -> None:
    logging.getLogger("websockets").setLevel(logging.CRITICAL)
    async with websockets.serve(handle, HOST, PORT):
        print(f"WebSocket collector (lab) on ws://{HOST}:{PORT}")
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
