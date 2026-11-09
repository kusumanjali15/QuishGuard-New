"""Stage 14.2: load-time characteristic detectors over the snapshots columns.

Each detector takes the sample DataFrame and returns a boolean pandas Series
aligned to df.index. PASSIVE / at-capture only. Constants below are the tunable
rule parameters.

Brand list (#7): Check Point Research Brand Phishing Rankings, Q2 and Q3 2024
(bracketing this dataset's July-August 2024 capture window) + LINE for Taiwan.
  https://blog.checkpoint.com/research/ (Q2 and Q3 2024 brand phishing reports)
"""

import math
import re
from urllib.parse import urlsplit

import pandas as pd

from quishguard.snapshots import _as_list, _s

# ----------------------------------------------------------------- tunables
CAPTCHA_WIDGET_HOSTS = ("recaptcha", "hcaptcha", "turnstile")           # #2a kit gate
CAPTCHA_TEXT_MARKERS = ("not a robot", "verify you are human", "i am human")  # extracted_text only
CLOUDFLARE_HOSTS = ("challenges.cloudflare.com",)                        # #2b interstitial
CLOUDFLARE_TEXT_MARKERS = ("checking your browser", "just a moment", "cloudflare", "ray id")

IDENTIFIER_TYPES = ("email",)
IDENTIFIER_HINTS = ("email", "user", "login", "phone", "account")

PAYMENT_AUTOCOMPLETE = ("cc-number", "cc-exp", "cc-csc")
LINKING_CODE_TERMS = ("linking code", "device code", "pair code", "pairing code",
                      "link your account", "connect your account", "link code")
PAYMENT_TERMS = ("card number", "credit card", "cvv", "cvc", "expiry date",
                 "billing address", "amount due", "pay now", "payment details")
ZH_CODE_PAYMENT_TERMS = ("驗證碼", "信用卡", "卡號", "付款", "綁定")  # zh-TW: code / card / payment / bind
NON_CRED_TERMS = LINKING_CODE_TERMS + PAYMENT_TERMS + ZH_CODE_PAYMENT_TERMS

SCRIPT_HEAVY_BYTES = 20_000          # #4 default
SCRIPT_LOW_TEXT = 200                # #4 default
SCRIPT_SETTINGS = [(10_000, 100), (20_000, 200), (50_000, 500)]  # #4 sensitivity sweep

DEAD_TEXT_LEN = 50                   # #5b
PARKED_MARKERS = ("domain for sale", "parked", "account suspended", "not found",
                  "403 forbidden", "404 not found", "page not found")

BRAND_TERMS = ("microsoft", "apple", "google", "linkedin", "facebook", "whatsapp",
               "instagram", "amazon", "alibaba", "adobe", "twitter", "adidas", "dhl", "line")

OC2_PROBE_TOKENS = ("navigator.webdriver", "webdriver", "navigator.useragent",
                    "navigator.user_agent")

# tldextract with the bundled suffix list (no network at runtime)
import tldextract  # noqa: E402
_EXTRACT = tldextract.TLDExtract(suffix_list_urls=())


# ----------------------------------------------------------------- helpers
def _lower_list(cell) -> list[str]:
    return [_s(x).lower() for x in _as_list(cell)]


def _list_has(col: pd.Series, markers) -> pd.Series:
    res = [any(m in " ".join(_lower_list(cell)) for m in markers) for cell in col.tolist()]
    return pd.Series(res, index=col.index)


def _text_has(col: pd.Series, markers) -> pd.Series:
    s = col.fillna("").astype(str).str.lower()
    out = pd.Series(False, index=col.index)
    for m in markers:
        out |= s.str.contains(m, regex=False)
    return out


def _word_has(col: pd.Series, terms) -> pd.Series:
    """Whole-word match (so 'line' does not match 'online', 'apple' not 'pineapple')."""
    s = col.fillna("").astype(str).str.lower()
    out = pd.Series(False, index=col.index)
    for term in terms:
        out |= s.str.contains(r"\b" + re.escape(term) + r"\b", regex=True)
    return out


def _bool(col: pd.Series) -> pd.Series:
    return col.map(lambda x: bool(x) if (x is not None and x == x) else False).astype(bool)


def _int(col: pd.Series) -> pd.Series:
    return pd.to_numeric(col, errors="coerce").fillna(0)


def _reg_domain(value: str) -> str:
    """Registrable domain (eTLD+1) of a host or URL; '' if none."""
    netloc = urlsplit(value).netloc or value
    ext = _EXTRACT(netloc)
    return f"{ext.domain}.{ext.suffix}".lower() if ext.suffix else netloc.lower()


# ----------------------------------------------------------------- detectors
def has_identifier_field(df):
    res = []
    for cell in df["input_fields"].tolist():
        found = False
        for f in _as_list(cell):
            typ = _s(f.get("type")).lower()
            blob = " ".join(_s(f.get(k)).lower() for k in ("name", "placeholder", "autocomplete", "id"))
            if typ in IDENTIFIER_TYPES or any(h in blob for h in IDENTIFIER_HINTS):
                found = True
                break
        res.append(found)
    return pd.Series(res, index=df.index)


def _has_non_password_input(df):
    res = [any(_s(f.get("type")).lower() != "password" for f in _as_list(cell))
           for cell in df["input_fields"].tolist()]
    return pd.Series(res, index=df.index)


def _has_payment_autocomplete(df):
    res = [any(_s(f.get("autocomplete")).lower() in PAYMENT_AUTOCOMPLETE for f in _as_list(cell))
           for cell in df["input_fields"].tolist()]
    return pd.Series(res, index=df.index)


def password_present(df):            # #1c
    return _bool(df["has_password_field"])


def multi_step_no_password(df):      # #1a
    return has_identifier_field(df) & ~_bool(df["has_password_field"]) & (_int(df["input_count"]) > 0)


def no_input_fields(df):             # #1b
    return _int(df["input_count"]) == 0


def captcha_widget(df):              # #2a: kit's own CAPTCHA (recaptcha/hcaptcha/turnstile) or human-gate text
    host = (_list_has(df["external_script_urls"], CAPTCHA_WIDGET_HOSTS)
            | _list_has(df["iframe_srcs"], CAPTCHA_WIDGET_HOSTS)
            | _list_has(df["external_domains"], CAPTCHA_WIDGET_HOSTS))
    return host | _text_has(df["extracted_text"], CAPTCHA_TEXT_MARKERS)


def cloudflare_interstitial(df):     # #2b: hosting anti-bot page, not a kit gate
    host = (_list_has(df["external_script_urls"], CLOUDFLARE_HOSTS)
            | _list_has(df["iframe_srcs"], CLOUDFLARE_HOSTS)
            | _list_has(df["external_domains"], CLOUDFLARE_HOSTS))
    return host | _text_has(df["extracted_text"], CLOUDFLARE_TEXT_MARKERS)


def non_credential_lure(df, use_autocomplete: bool = True):   # #3
    signal = _text_has(df["extracted_text"], NON_CRED_TERMS)
    if use_autocomplete:
        signal = signal | _has_payment_autocomplete(df)
    return signal & ~_bool(df["has_password_field"]) & _has_non_password_input(df)


def script_driven(df, bytes_min: int = SCRIPT_HEAVY_BYTES, text_max: int = SCRIPT_LOW_TEXT):  # #4
    return ((_int(df["inline_scripts_total_bytes"]) > bytes_min)
            & (_int(df["input_count"]) == 0) & (_int(df["form_count"]) == 0)
            & (_int(df["text_length"]) < text_max))


def dead_strong(df):                 # #5a: HTTP >= 400 or no HTML
    return (_int(df["http_status"]) >= 400) | ~_bool(df["has_html"])


def dead_weak(df):                   # #5b: little text or a parked-title marker
    return (_int(df["text_length"]) < DEAD_TEXT_LEN) | _text_has(df["title"], PARKED_MARKERS)


def cross_site_form_action(df):      # #6 (descriptive; registrable-domain compare)
    pages = df["domain"].fillna("").astype(str).tolist()
    res = []
    for host, cell in zip(pages, df["form_actions"].tolist()):
        page_reg = _reg_domain(host)
        flag = False
        for a in _as_list(cell):
            a = _s(a).strip()
            if not a or a.startswith("#"):
                continue                      # empty / fragment -> same site
            if not urlsplit(a).netloc:
                continue                      # relative -> same site
            if _reg_domain(a) != page_reg:
                flag = True
                break
        res.append(flag)
    return pd.Series(res, index=df.index)


def brand_mention(df):               # #7 (descriptive, whole-word)
    return _word_has(df["title"], BRAND_TERMS) | _word_has(df["extracted_text"], BRAND_TERMS)


def automation_probe(df_heavy):      # OC2 (heavy sample only)
    res = []
    for cell in df_heavy["inline_scripts"].tolist():
        blob = cell.lower() if isinstance(cell, str) else " ".join(_lower_list(cell))
        res.append(any(tok in blob for tok in OC2_PROBE_TOKENS))
    return pd.Series(res, index=df_heavy.index)


LIGHT_DETECTORS = {
    "1c_password_present": password_present,
    "1a_multi_step_no_password": multi_step_no_password,
    "1b_no_input_fields": no_input_fields,
    "2a_captcha_widget": captcha_widget,
    "2b_cloudflare_interstitial": cloudflare_interstitial,
    "3_non_credential_lure": non_credential_lure,
    "4_script_driven": script_driven,
    "5a_dead_strong": dead_strong,
    "5b_dead_weak": dead_weak,
    "6_cross_site_form_action": cross_site_form_action,
    "7_brand_mention": brand_mention,
}


# ----------------------------------------------------------------- prevalence
def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for a proportion k/n, as fractions."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def prevalence_table(df: pd.DataFrame, detectors: dict | None = None) -> pd.DataFrame:
    """Each detector's prevalence per-capture and per-loose-unique-kit, with a
    Wilson 95% CI on the per-capture rate (dataset treated as a sample)."""
    from quishguard.snapshots import _dedup_keys

    detectors = LIGHT_DETECTORS if detectors is None else detectors
    uniq_mask = ~_dedup_keys(df, "loose").duplicated()
    n_cap, n_uni = len(df), int(uniq_mask.sum())
    rows = []
    for name, fn in detectors.items():
        s = fn(df)
        k_cap = int(s.sum())
        k_uni = int(s[uniq_mask].sum())
        lo, hi = wilson_ci(k_cap, n_cap)
        rows.append({
            "characteristic": name,
            "per_capture_%": round(100 * k_cap / n_cap, 2),
            "capture_95ci": f"{round(100*lo,2)}-{round(100*hi,2)}",
            "per_unique_kit_%": round(100 * k_uni / n_uni, 2) if n_uni else 0.0,
        })
    return pd.DataFrame(rows)


def script_driven_sweep(df: pd.DataFrame) -> pd.DataFrame:
    rows = [{"inline_bytes>": b, "text_len<": tx,
             "per_capture_%": round(100 * script_driven(df, b, tx).mean(), 2)}
            for b, tx in SCRIPT_SETTINGS]
    return pd.DataFrame(rows)


def non_credential_sweep(df: pd.DataFrame) -> pd.DataFrame:
    rows = [{"use_autocomplete": ac,
             "per_capture_%": round(100 * non_credential_lure(df, use_autocomplete=ac).mean(), 2)}
            for ac in (True, False)]
    return pd.DataFrame(rows)
