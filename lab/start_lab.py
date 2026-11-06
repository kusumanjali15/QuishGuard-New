"""Start all three lab servers in ONE terminal (127.0.0.1 only). Ctrl+C stops them.

Usage:  python lab\\start_lab.py
"""

import asyncio
import threading
import time
from http.server import HTTPServer

import bank_server
import attack_server
import ws_collector
import collector_server
import phish_server


class ExclusiveHTTPServer(HTTPServer):
    allow_reuse_address = False  # refuse to share a port (see run_experiment.py)


SERVERS = [
    ("Formosa Demo Bank (official)", bank_server.BankHandler, 8000),
    ("Phishing site", phish_server.PhishHandler, 8001),
    ("Attacker collector", collector_server.CollectorHandler, 8002),
    ("Attack-page server", attack_server.AttackHandler, 8003),
]

for name, handler, port in SERVERS:
    try:
        server = ExclusiveHTTPServer(("127.0.0.1", port), handler)
    except OSError:
        raise SystemExit(f"Port {port} is busy - is another lab server still running?")
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"{name:30} http://127.0.0.1:{port}")

threading.Thread(target=lambda: asyncio.run(ws_collector.main()), daemon=True).start()
print(f"{'WebSocket collector':30} ws://127.0.0.1:8004")
print("Lab running - Ctrl+C to stop.")
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nLab stopped.")
