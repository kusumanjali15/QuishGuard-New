"""E5: a tiny TRUSTED payment-processor server for the lab (127.0.0.1 only, port 8020).

Stands in for a hosted payment page (like Stripe Checkout): the card is typed on the processor's
OWN trusted origin and posted same-origin. :8020 is in rules.TRUSTED_PARTNER_ORIGINS.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HOST, PORT = "127.0.0.1", 8020
PAGE = Path(__file__).with_name("bank_pay.html")


class PayHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.split("?", 1)[0] == "/":
            self._reply(200, PAGE.read_bytes())
        else:
            self.send_error(404, "Not found")

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self._reply(200, b"<p>Trusted Pay (lab): payment received.</p>")

    def _reply(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


def main() -> None:
    HTTPServer((HOST, PORT), PayHandler).serve_forever()


if __name__ == "__main__":
    main()
