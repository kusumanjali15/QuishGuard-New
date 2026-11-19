"""Stage 14 explorer for the phishing-snapshots dataset.

  --estimate        per-column download sizes (footers only)
  --timecheck       shard timestamp ranges
  (no flag)         light sample: dedup + prevalence + form breakdown
  --verify          heavy first-pages: parser agreement
  --heavy-estimate  predict the heavy (~1000-row) download size
  --heavy           heavy ~1000-row sample: OC2 + exfil + exact-vs-loose dedup (with CIs)
  --export-labels   write lab/labels.csv (100 random) + lab/labels_supplement.csv (flagged)
  --precision       read both label sheets, report detector precision
"""

import sys
from pathlib import Path

from quishguard.snapshots import (dedup, dedup_counts, estimate_download, export_label_set,
                                   export_supplement, export_url_dataset, heavy_estimate,
                                   label_precision, load_heavy_sample, load_sample,
                                   shard_time_ranges, supplement_precision, verify_parsed_columns)
from quishguard.detectors import (automation_probe, exfil_endpoint_in_scripts,
                                   form_action_breakdown, non_credential_sweep,
                                   prevalence_table, script_driven_sweep, wilson_ci)

LABELS = Path(__file__).with_name("labels.csv")
SUPP = Path(__file__).with_name("labels_supplement.csv")

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

if "--heavy-estimate" in sys.argv:
    print(heavy_estimate())
    sys.exit(0)

if "--heavy" in sys.argv:
    print("Loading heavy ~1000-row sample (html + inline_scripts, earliest per shard)...")
    h = load_heavy_sample(k_per_shard=36)
    n = len(h)

    def pct_ci(series):
        k = int(series.sum())
        lo, hi = wilson_ci(k, n)
        return f"{round(100*k/n,1)}%  ({round(100*lo,1)}-{round(100*hi,1)})"

    exact_u, loose_u = len(dedup(h, "exact")), len(dedup(h, "loose"))
    print(f"heavy sample rows: {n}  (EARLIEST per shard - time-biased)")
    print(f"  on THESE rows: exact-dedup {exact_u} unique, loose-dedup {loose_u} unique / {n}")
    print(f"    -> loose merges {exact_u - loose_u} more than exact; true distinct count sits between them")
    print(f"  OC2 automation probe (webdriver/userAgent): {pct_ci(automation_probe(h))}")
    print(f"  exfil endpoint in scripts (telegram/discord/mailto): {pct_ci(exfil_endpoint_in_scripts(h))}")
    print("  (descriptive, heavy-sample only; floor for exfil since many kits exfil server-side)")
    sys.exit(0)

if "--export-urls" in sys.argv:
    out = Path(__file__).with_name("phishing_urls.csv")
    print("Extracting phishing URLs + features from all shards (~10-15 MB)...")
    _, k = export_url_dataset(out)
    print(f"wrote {k} phishing URLs to {out.name}  (phishing-only; open it in Excel)")
    sys.exit(0)

if "--export-labels" in sys.argv:
    _, k = export_label_set(LABELS)
    _, sk = export_supplement(SUPP)
    print(f"wrote {k} random rows to {LABELS.name} and {sk} flagged rows to {SUPP.name}.")
    print("Fill each truth column with 1 (really is) / 0 (false flag), save as CSV, then --precision.")
    sys.exit(0)

if "--precision" in sys.argv:
    print("Random 100-row sheet:")
    print(label_precision(LABELS).to_string(index=False))
    if SUPP.exists():
        print("\nFlagged supplement (rare detectors):")
        print(supplement_precision(SUPP).to_string(index=False))
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
