"""Stage 13: WHALE-style STATIC-stage baseline on the Mendeley 'Web page phishing
detection' dataset (Hannousse & Yahiouche, arXiv 2010.12847; HF pirocheto/phishing-url).

11,430 URLs, balanced 50/50, 87 features in three groups:
  - 56 URL syntax/structure features
  - 24 page-content features
  - 7 external-query features (whois, domain age, web traffic, page rank, ...)

This is a BASELINE (what URL/static analysis can do), sklearn, no torch. The point
of the project is that behaviour beats this; here we just measure the static ceiling.
"""

import pandas as pd

BASE = "hf://datasets/pirocheto/phishing-url/data"

EXTERNAL_FEATURES = [
    "whois_registered_domain", "domain_registration_length", "domain_age",
    "web_traffic", "dns_record", "google_index", "page_rank",
]
CONTENT_FEATURES = [
    "nb_hyperlinks", "ratio_intHyperlinks", "ratio_extHyperlinks", "ratio_nullHyperlinks",
    "nb_extCSS", "ratio_intRedirection", "ratio_extRedirection", "ratio_intErrors",
    "ratio_extErrors", "login_form", "external_favicon", "links_in_tags", "submit_email",
    "ratio_intMedia", "ratio_extMedia", "sfh", "iframe", "popup_window", "safe_anchor",
    "onmouseover", "right_clic", "empty_title", "domain_in_title", "domain_with_copyright",
]
NON_FEATURE = {"url", "status"}


def load():
    """Load the pre-split train/test frames from Hugging Face (tiny, ~1.2 MB)."""
    train = pd.read_parquet(f"{BASE}/train.parquet")
    test = pd.read_parquet(f"{BASE}/test.parquet")
    return train, test


def feature_sets(columns) -> dict[str, list[str]]:
    """Three nested feature sets. 'url_only' is the honest ON-DEVICE set (no external
    queries, no page-content); 'all' is the full benchmark."""
    allf = [c for c in columns if c not in NON_FEATURE]
    url_only = [c for c in allf if c not in CONTENT_FEATURES and c not in EXTERNAL_FEATURES]
    url_content = [c for c in allf if c not in EXTERNAL_FEATURES]
    return {"url_only (56)": url_only, "url+content (80)": url_content, "all (87)": allf}


def _metrics(y_true, y_pred) -> dict:
    from sklearn.metrics import (accuracy_score, f1_score, precision_score, recall_score)
    return {
        "accuracy": round(accuracy_score(y_true, y_pred), 4),
        "precision": round(precision_score(y_true, y_pred), 4),
        "recall": round(recall_score(y_true, y_pred), 4),
        "f1": round(f1_score(y_true, y_pred), 4),
    }


def run(train=None, test=None) -> pd.DataFrame:
    """Train LogisticRegression and HistGradientBoosting on each feature set; report
    test-split metrics. Uses the dataset's OWN train/test split (it's a benchmark)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if train is None or test is None:
        train, test = load()
    y_tr = (train["status"] == "phishing").astype(int)
    y_te = (test["status"] == "phishing").astype(int)

    models = {
        "logreg": make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000)),
        "hist_gbm": HistGradientBoostingClassifier(random_state=0),
    }
    rows = []
    for fs_name, feats in feature_sets(train.columns).items():
        for m_name, model in models.items():
            model.fit(train[feats], y_tr)
            pred = model.predict(test[feats])
            rows.append({"features": fs_name, "model": m_name, **_metrics(y_te, pred)})
    return pd.DataFrame(rows)


def confusion(features_key="url_only (56)", model_name="hist_gbm", train=None, test=None):
    """Confusion matrix for one setting (default: the on-device url-only HGB)."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import confusion_matrix
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    if train is None or test is None:
        train, test = load()
    y_tr = (train["status"] == "phishing").astype(int)
    y_te = (test["status"] == "phishing").astype(int)
    feats = feature_sets(train.columns)[features_key]
    model = (make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
             if model_name == "logreg" else HistGradientBoostingClassifier(random_state=0))
    model.fit(train[feats], y_tr)
    cm = confusion_matrix(y_te, model.predict(test[feats]))
    return pd.DataFrame(cm, index=["true_legit", "true_phish"],
                        columns=["pred_legit", "pred_phish"])
