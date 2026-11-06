"""Stage 11: static server for lab attack/harmless test pages (127.0.0.1:8003).

GET /<name>.html  -> serve lab/attacks/<name>.html
POST (any path)   -> 200 OK, no logging  (so a BENIGN page's own same-origin
                     send succeeds without ever touching the attacker log)
These pages exist only to test QuishGuard's defence.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8003
ATTACKS_DIR = Path(__file__).with_name("attacks")

# A 1x1 transparent GIF, so image-pixel requests get a valid response.
ONE_PIXEL_GIF = bytes.fromhex(
    "47494638396101000100800000000000ffffff21f90401000000002c"
    "00000000010001000002024401003b"
)


class AttackHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        name = Path(self.path.lstrip("/").split("?")[0]).name  # basename only (no traversal)
        page = ATTACKS_DIR / name
        if not name.endswith(".html"):   # analytics pixel etc.: return a 1x1 gif
            self.send_response(200)
            self.send_header("Content-Type", "image/gif")
            self.send_header("Content-Length", str(len(ONE_PIXEL_GIF)))
            self.end_headers()
            self.wfile.write(ONE_PIXEL_GIF)
            return
        if not page.is_file():
            self.send_error(404, "Not found")
            return
        body = page.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)           # read and discard (a benign self-send)
        self.send_response(204)           # No Content
        self.end_headers()


def main() -> None:
    print(f"Attack-page server (lab) on http://{HOST}:{PORT}")
    HTTPServer((HOST, PORT), AttackHandler).serve_forever()


if __name__ == "__main__":
    main()
