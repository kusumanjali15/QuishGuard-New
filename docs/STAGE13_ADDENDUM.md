# Stage 13 addendum - static URL stage under an honest operating point

**This is the STATIC stage, NOT Stage 15.** Stage 13 reported balanced accuracy on the
dataset's own random split. This addendum re-evaluates the same static URL stage the way the
paper needs it: a hand-rule -> LogisticRegression -> LightGBM progression, a DOMAIN-DISJOINT
split (grouped by eTLD+1 from the url column, so the same site cannot appear in train and
test), and **recall at a fixed low false-positive rate** (1% and 0.1%), averaged over 10 runs.
It motivates the behaviour layer; it does not use any behaviour features.

Data: pirocheto/phishing-url (Hannousse & Yahiouche, Mendeley c2gw7fy2j4), 11,430 URLs, balanced.
Code: `src/quishguard/urlmodel.py`, run via `PYTHONPATH=src python lab/run_urlmodel.py`.

## url_only (56 features, ON-DEVICE) - domain-disjoint, 10 runs (mean +/- std)

| model     | AUC          | recall@1% FPR | recall@0.1% FPR |
|-----------|--------------|---------------|-----------------|
| hand-rule | 0.756 ±0.036 | 0.174 ±0.092  | 0.030 ±0.041    |
| LogReg    | 0.914 ±0.033 | 0.462 ±0.072  | 0.208 ±0.110    |
| LightGBM  | 0.947 ±0.017 | 0.559 ±0.068  | 0.258 ±0.138    |

## all (87 features, +whois/page-rank/web-traffic/content) - domain-disjoint, 10 runs

| model     | AUC          | recall@1% FPR | recall@0.1% FPR |
|-----------|--------------|---------------|-----------------|
| hand-rule | 0.756 ±0.036 | 0.174 ±0.092  | 0.030 ±0.041    |
| LogReg    | 0.980 ±0.006 | 0.697 ±0.087  | 0.311 ±0.163    |
| LightGBM  | 0.990 ±0.002 | 0.829 ±0.041  | 0.454 ±0.126    |

## url_only - RANDOM split (leakage check), 10 runs

| model     | AUC          | recall@1% FPR | recall@0.1% FPR |
|-----------|--------------|---------------|-----------------|
| hand-rule | 0.762 ±0.007 | 0.204 ±0.054  | 0.017 ±0.025    |
| LogReg    | 0.934 ±0.005 | 0.524 ±0.028  | 0.278 ±0.071    |
| LightGBM  | 0.972 ±0.003 | 0.661 ±0.020  | 0.338 ±0.110    |

## SHAP top-15 (LightGBM, url_only, domain split)

nb_www 1.08, phish_hints 0.73, length_hostname 0.50, domain_in_brand 0.48, nb_hyphens 0.43,
ratio_digits_host 0.41, nb_slash 0.37, longest_words_raw 0.36, length_words_raw 0.31,
longest_word_path 0.27, ratio_digits_url 0.24, nb_dots 0.24, nb_redirection 0.24, nb_qm 0.21,
https_token 0.20.

## Takeaways (honest)

1. **Rules -> ML is a real gain:** on-device recall@1% FPR rises 0.17 (rule) -> 0.46 (LogReg)
   -> 0.56 (LightGBM).
2. **But the on-device ceiling is low at a realistic operating point.** The best on-device model
   catches only ~56% of phishing at 1% FPR and ~26% at 0.1% FPR. Stage 13's balanced-accuracy
   "~91%" does not survive a fixed low FPR on a domain-disjoint split. **This is the gap the
   runtime behaviour layer exists to close** (see RQ3 coverage, STAGE14B_NOTES.md).
3. **Random splits inflate.** LightGBM url_only recall@1% FPR is 0.66 random vs 0.56
   domain-disjoint - ~10 points of optimism from letting a domain sit in both sides.
4. **The extra +27 points to 0.83 need off-device features** (whois, page rank, web traffic,
   rendered content) - not available to an on-device QR-time check.

Note: 0.1% FPR is estimated from ~1,700 test negatives per run, so its variance is high; treat
the 1% FPR column as the headline operating point.
