"""Stage 13: run the static-stage URL baseline on pirocheto/phishing-url.

Usage:  python lab\\run_urlbaseline.py
"""

from quishguard.urlbaseline import confusion, run

print("Training static-stage URL baseline (Mendeley / pirocheto-phishing-url)...\n")
print(run().to_string(index=False))
print("\nConfusion matrix - on-device setting (url_only, hist_gbm):")
print(confusion().to_string())
print("\nNotes:")
print(" - Balanced 50/50 set, dataset's own train/test split (a benchmark, not our data).")
print(" - 'url_only (56)' is the honest ON-DEVICE number: no external queries (whois, page")
print("   rank, web traffic) and no page-content features, which WHALE's on-device static")
print("   stage also cannot cheaply get. 'all (87)' shows the ceiling WITH those.")
print(" - This is a BASELINE: the project's claim is that runtime BEHAVIOUR catches what")
print("   URL/static analysis misses, not that this number is high.")
