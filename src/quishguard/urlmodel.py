"""Stage 13 ADDENDUM: LightGBM static-stage URL model, evaluated honestly.

Upgrades the Stage 13 baseline (LogReg / HistGradientBoosting on the dataset's own
random split, balanced accuracy) to:
  - a hand-rule heuristic  ->  LogisticRegression  ->  LightGBM  (rules to ML),
  - a DOMAIN-DISJOINT split (grouped by eTLD+1 from the url column) so the same site
    cannot sit in both train and test,
  - recall at a fixed low false-positive rate (1% and 0.1%) - the realistic operating point,
  - averaged over 10 runs (different grouped splits; mean +/- std),
  - SHAP on the LightGBM to show which URL features drive detection.

Data: pirocheto/phishing-url (Hannousse & Yahiouche, Mendeley c2gw7fy2j4), local parquet
in lab15_data/. This is the STATIC stage; the project's claim is that runtime behaviour
(RQ3 coverage) catches what the URL stage misses, not that this number is high.
"""
from pathlib import Path
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[2]
DATA = HERE / "lab15_data"

EXTERNAL = ["whois_registered_domain", "domain_registration_length", "domain_age",
            "web_traffic", "dns_record", "google_index", "page_rank"]
CONTENT = ["nb_hyperlinks", "ratio_intHyperlinks", "ratio_extHyperlinks", "ratio_nullHyperlinks",
           "nb_extCSS", "ratio_intRedirection", "ratio_extRedirection", "ratio_intErrors",
           "ratio_extErrors", "login_form", "external_favicon", "links_in_tags", "submit_email",
           "ratio_intMedia", "ratio_extMedia", "sfh", "iframe", "popup_window", "safe_anchor",
           "onmouseover", "right_clic", "empty_title", "domain_in_title", "domain_with_copyright"]
NON = {"url", "status"}


def load():
    tr = pd.read_parquet(DATA / "train.parquet")
    te = pd.read_parquet(DATA / "test.parquet")
    return pd.concat([tr, te], ignore_index=True)


def feature_sets(columns):
    allf = [c for c in columns if c not in NON]
    url_only = [c for c in allf if c not in CONTENT and c not in EXTERNAL]
    url_content = [c for c in allf if c not in EXTERNAL]
    return {"url_only (56)": url_only, "url+content (80)": url_content, "all (87)": allf}


_EX = None
def domains(urls):
    """eTLD+1 per row (offline, bundled public-suffix snapshot); IP/fqdn fallback."""
    global _EX
    import tldextract
    if _EX is None:
        _EX = tldextract.TLDExtract(suffix_list_urls=())
    out = []
    for u in urls:
        s = str(u)
        r = _EX(s if "//" in s else "http://" + s)
        out.append(r.top_domain_under_public_suffix or r.ipv4 or r.fqdn or s)
    return np.array(out)


def rule_score(df):
    """Classic hand-written URL red-flags (higher = more phishing). A sweepable score so
    the rule gets its own ROC, comparable to the models."""
    s = np.zeros(len(df))
    s += df["ip"].astype(float)
    s += (df["nb_at"] > 0).astype(float)
    s += df["prefix_suffix"].astype(float)
    s += df["shortening_service"].astype(float)
    s += df["suspecious_tld"].astype(float)
    s += df["punycode"].astype(float)
    s += df["tld_in_subdomain"].astype(float)
    s += df["abnormal_subdomain"].astype(float)
    s += (df["nb_subdomains"] >= 3).astype(float)
    s += (df["ratio_digits_url"] > 0.3).astype(float)
    s += (df["length_url"] > 75).astype(float)
    s += (df["phish_hints"] > 0).astype(float)
    s += (df["nb_dots"] >= 4).astype(float)
    return s


def recall_at_fpr(y, score, target):
    from sklearn.metrics import roc_curve
    fpr, tpr, _ = roc_curve(y, score)
    ok = np.where(fpr <= target)[0]
    return float(tpr[ok].max()) if len(ok) else 0.0


def _fit(Xtr, ytr):
    from lightgbm import LGBMClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    lgb = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                         random_state=0, verbose=-1)
    lgb.fit(Xtr, ytr)
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    lr.fit(Xtr, ytr)
    return lgb, lr


def evaluate(feature_key="url_only (56)", n_runs=10, fprs=(0.01, 0.001), grouped=True):
    from sklearn.model_selection import GroupShuffleSplit, ShuffleSplit
    from sklearn.metrics import roc_auc_score
    full = load()
    feats = feature_sets(full.columns)[feature_key]
    y = (full["status"] == "phishing").astype(int).values
    X = full[feats].values
    grp = domains(full["url"].values) if grouped else None
    rows = []
    for run in range(n_runs):
        if grouped:
            tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=run).split(X, y, grp))
        else:
            tr, te = next(ShuffleSplit(n_splits=1, test_size=0.3, random_state=run).split(X, y))
        lgb, lr = _fit(X[tr], y[tr])
        yte = y[te]
        scores = {"rule": rule_score(full.iloc[te]),
                  "logreg": lr.predict_proba(X[te])[:, 1],
                  "lightgbm": lgb.predict_proba(X[te])[:, 1]}
        for name, sc in scores.items():
            rec = {"run": run, "model": name, "auc": roc_auc_score(yte, sc)}
            for f in fprs:
                rec[f"recall@{f:g}FPR"] = recall_at_fpr(yte, sc, f)
            rows.append(rec)
    df = pd.DataFrame(rows)
    agg = df.drop(columns="run").groupby("model").agg(["mean", "std"])
    order = ["rule", "logreg", "lightgbm"]
    return df, agg.reindex(order)


def shap_top(feature_key="url_only (56)", k=15, sample=1500):
    import shap
    from sklearn.model_selection import GroupShuffleSplit
    full = load()
    feats = feature_sets(full.columns)[feature_key]
    y = (full["status"] == "phishing").astype(int).values
    grp = domains(full["url"].values)
    tr, te = next(GroupShuffleSplit(1, test_size=0.3, random_state=0).split(full[feats], y, grp))
    lgb, _ = _fit(full[feats].values[tr], y[tr])
    Xte = full[feats].iloc[te]
    if len(Xte) > sample:
        Xte = Xte.sample(sample, random_state=0)
    sv = shap.TreeExplainer(lgb).shap_values(Xte)
    sv1 = sv[1] if isinstance(sv, list) else sv
    imp = np.abs(sv1).mean(0)
    idx = np.argsort(imp)[::-1][:k]
    return [(feats[i], round(float(imp[i]), 4)) for i in idx]
