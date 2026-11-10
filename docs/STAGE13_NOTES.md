# Stage 13 notes - static-stage URL baseline

Dataset: Mendeley "Web page phishing detection" (Hannousse & Yahiouche, arXiv 2010.12847),
HF mirror `pirocheto/phishing-url`. 11,430 URLs, **balanced 50/50**, 87 features
(56 URL-syntax + 24 page-content + 7 external-query). Dataset's own train/test split.
sklearn only, no torch. This is a BASELINE (the static ceiling), not the contribution.

## Results (HistGradientBoosting beats LogisticRegression everywhere)

| Feature set | accuracy | precision | recall | F1 |
|---|---|---|---|---|
| url_only (56) - ON-DEVICE | 0.9107 | 0.9032 | 0.9199 | 0.9115 |
| url+content (80)          | 0.9419 | 0.9417 | 0.9422 | 0.9420 |
| all (87)                  | 0.9708 | 0.9669 | 0.9751 | 0.9710 |

Confusion matrix, url_only / HGB (test n=3772):
- true_legit: 1700 pred_legit, 186 pred_phish  (186 false alarms)
- true_phish:  151 pred_legit, 1735 pred_phish  (151 phishing missed)

## Takeaways for the paper

1. **On-device URL ceiling ~91% (F1 0.91).** Pure URL-string features only.
2. **The +6 points to 97% require signals WHALE can't cheaply get on-device:** +3 from
   page-content (needs rendering), +3 from external queries (whois, page-rank, web-traffic).
   So "97%" is not an on-device number.
3. **Even 91% misses ~8% of phishing** (151/1886) - the gap runtime behaviour should close.

## Honest caveats

- Balanced 50/50 and ~2020-era URLs. Real base rate makes phishing RARE, so at a fixed low
  FPR recall would be lower; report recall@fixed-FPR on an imbalanced split for the paper.
- We reproduced the CLASSIFIER, not the feature extraction (features came pre-computed).
- General URLs, not QR-reachable specifically.
- URL-BERT (CrabInHoney/urlbert-tiny-v4) remains parked as an optional extra column.
