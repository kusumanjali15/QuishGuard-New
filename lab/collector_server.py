"""Stage 2: the lab ATTACKER COLLECTOR - receives stolen (fake) data (127.0.0.1 only).

It logs every POST to logs/attacker.log, then redirects the victim to the real
bank so nothing looks wrong - the same trick real phishing kits use.
"""

from datetime import datetime
from urllib.parse import urlsplit, parse_qs
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from quishguard.forms import parse_form_body
from quishguard.leaklog import append_log_entry

HOST = "127.0.0.1"  # loopback only
PORT = 8002
REAL_BANK = "http://127.0.0.1:8000/"

# A 1x1 transparent GIF, so image-pixel requests get a valid response.
ONE_PIXEL_GIF = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c"
    "00000000010001000002024401003b"
)
LOG_PATH = Path(__file__).resolve().parent.parent / "logs" / "attacker.log"


class CollectorHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        """Image-pixel / GET leaks: log any query-string data, return a pixel."""
        query = urlsplit(self.path).query
        if query:
            fields = {k: v[0] for k, v in parse_qs(query, keep_blank_values=True).items()}
            entry = {
                "time": datetime.now().isoformat(timespec="seconds"),
                "server": "collector",
                "path": self.path,
                "origin": self.headers.get("Origin"),
                "fields": fields,
            }
            append_log_entry(LOG_PATH, entry)
            print(f"[collector] LEAK logged (GET): {fields}")
        self.send_response(200)
        self.send_header("Content-Type", "image/gif")
        self.send_header("Content-Length", str(len(ONE_PIXEL_GIF)))
        self.end_headers()
        self.wfile.write(ONE_PIXEL_GIF)

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
