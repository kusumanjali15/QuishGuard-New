"""Stage 13 ADDENDUM: LightGBM static-stage URL model, honest evaluation.
Run:  PYTHONPATH=src python lab/run_urlmodel.py
Needs lab15_data/{train,test}.parquet (pirocheto/phishing-url) and the qg15 venv
(pyarrow pandas scikit-learn lightgbm shap tldextract).
"""
import warnings; warnings.filterwarnings("ignore")
import pandas as pd
from quishguard import urlmodel as M

pd.set_option("display.width", 160, "display.max_columns", 20)

def show(agg, title):
    print(f"\n### {title}")
    out = agg.copy(); out.columns = [f"{a}.{b}" for a, b in out.columns]
    print(out.round(3).to_string())
    return out

print("=" * 68, "\nSTAGE 13 ADDENDUM - static URL stage - DOMAIN-DISJOINT split - 10 runs\n", "=" * 68)
runs = []
df, agg   = M.evaluate("url_only (56)", n_runs=10, grouped=True);  show(agg,  "url_only (56)  [on-device]  domain-disjoint"); df["setting"]="url_only/domain"
df2, agg2 = M.evaluate("all (87)",      n_runs=10, grouped=True);  show(agg2, "all (87)  [+whois/pagerank/content]  domain-disjoint"); df2["setting"]="all/domain"
dfr, aggr = M.evaluate("url_only (56)", n_runs=10, grouped=False); show(aggr, "url_only (56)  RANDOM split  [leakage check]"); dfr["setting"]="url_only/random"
pd.concat([df, df2, dfr], ignore_index=True).to_csv("lab15_data/stage13_addendum_runs.csv", index=False)
print("\n### SHAP top-15  (LightGBM, url_only, domain split)")
for name, val in M.shap_top("url_only (56)"):
    print(f"  {val:6.3f}  {name}")
print("\nper-run results saved to lab15_data/stage13_addendum_runs.csv")
