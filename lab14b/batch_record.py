"""Stage 14b batch: record every extracted kit, aggregate the RQ3/RQ4 signal.

Subprocesses record_kit.py per kit (with a timeout to kill hangs), reads the traces, writes
lab14b/traces/_summary.csv + prints aggregate stats. Run DISCONNECTED, after egress_test says
ISOLATED. Traces may hold attacker addresses (gitignored); the summary is booleans only.
"""
import csv, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TRACES = HERE / "traces"; TRACES.mkdir(exist_ok=True)
KITS = Path.home() / "dynapd_kits" / "raw_kits_unzipped"
PER_KIT_TIMEOUT = 45  # scaled run: dead-offline kits exit fast; 45s caps the rare hang

def classify(tr):
    sends = tr.get("sends", [])
    host = next((s["dest_host"] for s in sends if s.get("dest_host","").startswith("127.0.0.1")), None)
    cred = [s for s in sends if s.get("carries_fake_value")]
    return {
        "kit_id": tr.get("kit_id"), "entry": tr.get("entry"), "n_sends": len(sends),
        "cred_submitted": bool(cred),
        "cred_same_origin_post": any(s.get("method")=="POST" and s.get("dest_host")==host for s in cred),
        "cred_cross_origin": any(s.get("dest_host")!=host for s in cred),
        "mail_exfil": tr.get("mail_exfil_captured", False),
    }

def blank(name): return {"kit_id": name, "entry": None, "n_sends": 0, "cred_submitted": False,
                         "cred_same_origin_post": False, "cred_cross_origin": False, "mail_exfil": False}

def main():
    kits = sorted(d for d in KITS.iterdir() if d.is_dir())
    rows = []
    for i, kit in enumerate(kits, 1):
        out = TRACES / f"{kit.name}.json"
        try:
            subprocess.run([sys.executable, str(HERE/"record_kit.py"), str(kit), "--out", str(out)],
                           timeout=PER_KIT_TIMEOUT, cwd=str(ROOT),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        try:
            rows.append(classify(json.loads(out.read_text())) if out.exists() else blank(kit.name))
        except Exception:
            rows.append(blank(kit.name))
        r = rows[-1]
        print(f"[{i}/{len(kits)}] {kit.name} cred={r['cred_submitted']} "
              f"same_post={r['cred_same_origin_post']} cross={r['cred_cross_origin']} mail={r['mail_exfil']}")
    with (TRACES/"_summary.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    n = len(rows); sub = sum(r["cred_submitted"] for r in rows)
    print("\n==== RQ3/RQ4 aggregate ====")
    print(f"kits recorded:                   {n}")
    print(f"submitted credentials:           {sub}/{n}")
    print(f"  via same-origin POST (sensor-coverable): {sum(r['cred_same_origin_post'] for r in rows)}")
    print(f"  with a cross-origin client send:         {sum(r['cred_cross_origin'] for r in rows)}")
    print(f"server-side mail exfil captured: {sum(r['mail_exfil'] for r in rows)}")
    print(f"summary CSV: {TRACES/'_summary.csv'}")

if __name__ == "__main__":
    main()
