"""Stage 9: run every scenario WITHOUT and WITH protection; print a results table.

Starts the three lab servers itself (127.0.0.1 only) - stop your own copies first.
Usage:  python run_experiment.py
"""

import asyncio
import contextlib
import csv
import io
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT / "lab"))  # so we can import the lab servers

import bank_server, collector_server, phish_server  # noqa: E402

from quishguard.experiment import SCENARIOS, evaluate  # noqa: E402
from quishguard.guard import Guard  # noqa: E402
from quishguard.qr import decode_qr  # noqa: E402
from quishguard.rules import ScanContext  # noqa: E402
from quishguard.victim import visit_and_login  # noqa: E402

USERNAME, PASSWORD = "demo_user_01", "Lab-Pass-4821"
EXPERIMENT_LOG = ROOT / "logs" / "experiment_attacker.log"
RESULTS_CSV = ROOT / "results" / "experiment.csv"
bank_logins = 0  # counted by the bank server itself


class CountingBank(bank_server.BankHandler):
    def do_POST(self) -> None:
        global bank_logins
        bank_logins += 1
        super().do_POST()


class ExclusiveHTTPServer(HTTPServer):
    """Refuse to share a port. Plain HTTPServer sets SO_REUSEADDR, which on
    Windows lets two servers listen on the same port - and the old one may win."""
    allow_reuse_address = False


def start_servers() -> None:
    """Run the three lab servers in background threads."""
    collector_server.LOG_PATH = EXPERIMENT_LOG  # separate log, wiped each run
    EXPERIMENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_LOG.write_text("", encoding="utf-8")
    for handler, port in [(CountingBank, 8000), (phish_server.PhishHandler, 8001),
                          (collector_server.CollectorHandler, 8002)]:
        handler.log_message = lambda *args: None  # silence per-request logs
        try:
            server = ExclusiveHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            sys.exit(f"Port {port} is busy - stop your lab servers first (Ctrl+C), then rerun.")
        threading.Thread(target=server.serve_forever, daemon=True).start()


def leak_count() -> int:
    return len(EXPERIMENT_LOG.read_text(encoding="utf-8").splitlines())


async def run_one(scenario, protected: bool) -> dict:
    global bank_logins
    url = decode_qr(ROOT / "lab" / "qr" / scenario.qr_file)
    guard = Guard(scan=ScanContext(from_qr=True), typed_values=[PASSWORD]) if protected else None
    leaks_before, bank_logins = leak_count(), 0

    with contextlib.redirect_stdout(io.StringIO()):  # hide server prints during the run
        await visit_and_login(url, USERNAME, PASSWORD, guard=guard)
    await asyncio.sleep(0.3)  # let the servers finish writing

    leaked = leak_count() - leaks_before
    ok, note = evaluate(scenario.kind, protected, leaked, bank_logins)
    blocked = sum(line.startswith("BLOCK") for line in guard.log) if guard else 0
    return {"scenario": scenario.name, "kind": scenario.kind,
            "protection": "on" if protected else "off", "leaked": leaked,
            "bank_logins": bank_logins, "blocked_sends": blocked,
            "result": "PASS" if ok else "FAIL", "note": note}


def print_table(rows: list[dict]) -> None:
    print(f"\n{'SCENARIO':24} {'KIND':6} {'PROT':4} {'LEAKED':6} {'BANK':4} {'BLOCKED':7} RESULT")
    for r in rows:
        print(f"{r['scenario']:24} {r['kind']:6} {r['protection']:4} {r['leaked']:>6} "
              f"{r['bank_logins']:>4} {r['blocked_sends']:>7} {r['result']}  ({r['note']})")
    failed = sum(r["result"] == "FAIL" for r in rows)
    print(f"\n{len(rows) - failed}/{len(rows)} passed")


async def main() -> int:
    start_servers()
    rows = [await run_one(s, protected) for s in SCENARIOS for protected in (False, True)]
    print_table(rows)

    RESULTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"saved {RESULTS_CSV.relative_to(ROOT)}")
    return 1 if any(r["result"] == "FAIL" for r in rows) else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
