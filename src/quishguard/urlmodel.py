"""Stage 13: a pretrained URL-only phishing classifier (Hugging Face).

Model: CrabInHoney/urlbert-tiny-v4-phishing-classifier (BERT, 3.7M params).
Labels: LABEL_0 = legitimate, LABEL_1 = phishing.

A URL-only model judges the string alone. It knows nothing about what the page
DOES - so it cannot see a same-origin theft, a delayed form, or a localhost lab
URL. Use it as one more signal, never as the whole answer.
"""

from functools import lru_cache

MODEL_NAME = "CrabInHoney/urlbert-tiny-v4-phishing-classifier"


def normalize_url_for_model(url: str) -> str:
    """The model was trained on bare URLs (no scheme). Strip http(s):// ."""
    for scheme in ("https://", "http://"):
        if url.startswith(scheme):
            return url[len(scheme):]
    return url


@lru_cache(maxsize=1)
def _load():
    """Load tokenizer + model once (downloaded and cached on first use)."""
    import torch
    from transformers import BertForSequenceClassification, BertTokenizerFast

    tokenizer = BertTokenizerFast.from_pretrained(MODEL_NAME)
    model = BertForSequenceClassification.from_pretrained(MODEL_NAME)
    model.eval()  # inference mode
    return tokenizer, model, torch


def url_phishing_score(url: str) -> float:
    """Return the model's probability (0..1) that this URL is phishing."""
    tokenizer, model, torch = _load()
    inputs = tokenizer(normalize_url_for_model(url), return_tensors="pt",
                       truncation=True, max_length=64)
    with torch.no_grad():
        logits = model(**inputs).logits
    probs = torch.softmax(logits, dim=-1)[0]
    return float(probs[1])  # LABEL_1 = phishing
