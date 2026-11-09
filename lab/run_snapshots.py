"""Stage 14 explorer for the phishing-snapshots dataset.

  python lab\\run_snapshots.py --estimate         # per-column download sizes (footers only)
  python lab\\run_snapshots.py --timecheck        # shard timestamp ranges
  python lab\\run_snapshots.py                     # light sample: dedup + prevalence + form breakdown
  python lab\\run_snapshots.py --verify            # heavy first-pages: parser agreement
  python lab\\run_snapshots.py --heavy             # heavy sample: OC2 + exfil + exact-dedup bound
  python lab\\run_snapshots.py --export-labels     # write lab/labels.csv (100 random rows to label)
  python lab\\run_snapshots.py --precision         # read lab/labels.csv, report detector precision
"""

import sys
from pathlib import Path

from quishguard.snapshots import (dedup, dedup_counts, estimate_download, export_label_set,
                                   label_precision, load_heavy_sample, load_sample,
                                   shard_time_ranges, verify_parsed_columns)
from quishguard.detectors import (automation_probe, exfil_endpoint_in_scripts,
                                   form_action_breakdown, non_credential_sweep,
                                   prevalence_table, script_driven_sweep)

LABELS = Path(__file__).with_name("labels.csv")

if "--estimate" in sys.argv:
    est = estimate_download()
    print(f"selected (light): {est['selected_download_mb']} MB   all: {est['all_columns_mb']} MB")
    for c, mb in est["per_column_mb_top12"].items():
        print(f"  {c:28} {mb}")
    sys.exit(0)

if "--timecheck" in sys.argv:
    tr = shard_time_ranges()
    print(tr.to_string(index=False))
    print(f"\nmin_ts monotonic across shards: {tr['min_ts'].is_monotonic_increasing}")
    sys.exit(0)

if "--verify" in sys.argv:
    v = verify_parsed_columns()
    print(f"parse check on {len(v)} rows: {int(v['input_mismatch'].sum())} input, "
          f"{int(v['pw_mismatch'].sum())} password mismatches")
    sys.exit(0)

if "--heavy" in sys.argv:
    print("Loading heavy first-pages sample (html + inline_scripts)...")
    h = load_heavy_sample()
    exact_unique = len(dedup(h, "exact"))
    print(f"heavy sample rows: {len(h)}  (EARLIEST per shard - time-biased)")
    print(f"  exact-dedup unique: {exact_unique} / {len(h)}  "
          f"-> bounds how much loose dedup over-merges")
    print(f"  OC2 automation probe (navigator.webdriver/userAgent): {round(100*automation_probe(h).mean(),1)}%")
    print(f"  exfil endpoint in scripts (telegram/discord/mailto): {round(100*exfil_endpoint_in_scripts(h).mean(),1)}%")
    print("  (both heavy-sample, descriptive only)")
    sys.exit(0)

if "--export-labels" in sys.argv:
    path, k = export_label_set(LABELS)
    print(f"wrote {k} rows to {path}. Fill each truth:: column with 1 (really is) or 0 (false flag), then --precision.")
    sys.exit(0)

if "--precision" in sys.argv:
    print(label_precision(LABELS).to_string(index=False))
    sys.exit(0)

print("Loading LIGHT columns from all 28 shards...")
df = load_sample()
counts = dedup_counts(df)
print(f"\ntotal rows: {counts['none']}")
if "loose" in counts:
    u = counts["loose"]
    print(f"  loose dedup -> {u} unique pages ({round(100*u/counts['none'])}% of rows)")

print("\nPrevalence of load-time characteristics:")
print(prevalence_table(df).to_string(index=False))

fb, nforms = form_action_breakdown(df)
print(f"\nForm-action breakdown (among {nforms} pages with a form action):")
print(fb.to_string(index=False))

print("\n#4 script-driven sensitivity:");  print(script_driven_sweep(df).to_string(index=False))
print("\n#3 non-credential-lure sensitivity:");  print(non_credential_sweep(df).to_string(index=False))

print("\nCAVEATS:")
print(" - General phishing captured Jul-Aug 2024; NOT QR-reachable pages specifically.")
print(" - Passive, at-capture only (no interaction / no credential sends).")
print(" - '1c_password_present' ~ the dataset's own has_password_field column (not an independent")
print("   validation; the html parse check --verify is the real one).")
print(" - Loose dedup may OVER-MERGE dead/near-identical pages; see --heavy for an exact-dedup bound.")
