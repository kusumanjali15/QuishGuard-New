"""Stage 14 explorer for the phishing-snapshots dataset.

  python lab\\run_snapshots.py --estimate    # CHEAP: per-column download sizes (footers only)
  python lab\\run_snapshots.py --timecheck   # CHEAP: shard timestamp ranges
  python lab\\run_snapshots.py               # sample LIGHT columns, none/loose dedup
  python lab\\run_snapshots.py --verify      # small HEAVY first-pages sample: parse check
"""

import sys

from quishguard.snapshots import (dedup_counts, estimate_download, load_sample,
                                   shard_time_ranges, verify_parsed_columns)

if "--estimate" in sys.argv:
    print("Reading parquet footers only (no row data)...")
    est = estimate_download()
    print(f"  selected (light) download: {est['selected_download_mb']} MB")
    print(f"  all columns:               {est['all_columns_mb']} MB   (rows: {est['rows_total']})")
    print("  heaviest columns (MB):")
    for col, mb in est["per_column_mb_top12"].items():
        print(f"    {col:28} {mb}")
    sys.exit(0)

if "--timecheck" in sys.argv:
    tr = shard_time_ranges()
    print(tr.to_string(index=False))
    print(f"\nshards time-ordered (min_ts monotonic): {tr['min_ts'].is_monotonic_increasing}")
    sys.exit(0)

if "--verify" in sys.argv:
    v = verify_parsed_columns()
    nin, npw = int(v["input_mismatch"].sum()), int(v["pw_mismatch"].sum())
    print(f"parse check on {len(v)} rows (earliest per shard 0): "
          f"{nin} input-count mismatches, {npw} password-flag mismatches")
    bad = v[v["input_mismatch"] | v["pw_mismatch"]]
    print(bad.to_string(index=False) if len(bad) else "  (our parse agrees with the dataset columns)")
    sys.exit(0)

QUICK = "--quick" in sys.argv
shards = [0, 7, 14, 21] if QUICK else None
print(f"Loading LIGHT columns from {'4 spread shards (quick preview)' if QUICK else 'all 28 shards'}...")
df = load_sample(shards=shards)  # light columns
counts = dedup_counts(df)   # none + loose (exact needs html -> heavy sample)
print(f"\ntotal rows: {counts['none']}")
if "loose" in counts:
    u = counts["loose"]
    print(f"  loose dedup -> {u} unique pages ({round(100*u/counts['none'])}% of rows)")
print("  (exact dedup + OC2 inline-JS search need the html/inline_scripts blobs -> heavy sample)")
