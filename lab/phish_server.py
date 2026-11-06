"""Stage 2: the lab PHISHING site - serves a fake copy of the bank page (127.0.0.1 only)."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from quishguard.forms import parse_form_body

HOST = "127.0.0.1"  # loopback: only this computer can reach the server
PORT = 8001
PAGE = Path(__file__).with_name("phish_login.html")


class PhishHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        """Browser asks for a page: send the login page for "/"."""
        if self.path != "/":
            self.send_error(404, "Not found")
            return
        self._reply(200, PAGE.read_bytes())

    def do_POST(self) -> None:
        """Form submitted: read the body and print what the server received."""
        # Content-Length header says how many bytes the body has.
        length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(length).decode("utf-8")
        

        print(f"\n[phish] {self.command} {self.path}")
        print(f"[phish] Origin header: {self.headers.get('Origin')}")
        print(f"[phish] Content-Type:  {self.headers.get('Content-Type')}")
        print(f"[phish] raw body:      {raw_body}")
        fields = parse_form_body(raw_body)
        for name, value in fields.items():
            print(f"[phish] field {name} = {value}")

        self._reply(200, b"<p>Lab: phishing site received a POST.</p>")

    def _reply(self, status: int, body: bytes) -> None:
        """Send status line, headers, blank line, then the body."""
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main() -> None:
    server = HTTPServer((HOST, PORT), PhishHandler)
    print(f"Phishing site (lab) on http://{HOST}:{PORT}  - Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
