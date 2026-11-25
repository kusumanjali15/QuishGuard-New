"""Stage 14b SAFETY GATE: prove this environment has NO internet egress.

Run BEFORE every real-kit session. Exit 0 and print "ISOLATED" only if EVERY external
reach fails. Any success prints "NOT ISOLATED" and exits 1 - do not run kits until it is
ISOLATED. Pure stdlib; no network data leaves (these are connection ATTEMPTS that must fail).
"""

import socket
import sys
import urllib.request

TIMEOUT = 4  # seconds per probe


def tcp_fails(host: str, port: int) -> bool:
    """True if we CANNOT open a TCP connection (good - isolated)."""
    try:
        with socket.create_connection((host, port), timeout=TIMEOUT):
            return False  # connected -> egress exists -> BAD
    except OSError:
        return True


def dns_fails(name: str) -> bool:
    """True if we CANNOT resolve a public name (good). A local DNS sinkhole may still
    resolve it to the sink IP - that is NOT egress, so we also check the resolved IP is
    not a real external address by trying to connect (covered by tcp_fails)."""
    try:
        socket.getaddrinfo(name, 443, proto=socket.IPPROTO_TCP)
        return False  # resolved -> note it, but connection test is the real gate
    except OSError:
        return True


def http_fails(url: str) -> bool:
    """True if we CANNOT fetch a public URL (good - isolated)."""
    try:
        urllib.request.urlopen(url, timeout=TIMEOUT).read(1)
        return False  # fetched -> egress exists -> BAD
    except Exception:
        return True


def main() -> int:
    checks = [
        ("TCP 1.1.1.1:443", tcp_fails("1.1.1.1", 443)),
        ("TCP 8.8.8.8:53", tcp_fails("8.8.8.8", 53)),
        ("HTTP example.com", http_fails("http://example.com")),
        ("HTTP cloudflare dns", http_fails("https://1.1.1.1")),
    ]
    dns = dns_fails("www.google.com")  # informational only

    print("Egress gate (each line must be BLOCKED):")
    isolated = True
    for name, failed in checks:
        print(f"  {name:22} {'BLOCKED' if failed else 'REACHABLE  <-- EGRESS!'}")
        isolated = isolated and failed
    print(f"  (info) DNS resolves    {'no' if dns else 'yes - ok if a local sinkhole; the TCP/HTTP checks are the gate'}")

    if isolated:
        print("\nISOLATED - no egress reached. Safe to run kits.")
        return 0
    print("\nNOT ISOLATED - something is reachable. DO NOT run kits. Fix isolation (disconnect the machine).")
    return 1


if __name__ == "__main__":
    sys.exit(main())
