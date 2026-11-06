"""Stage 13: run the pretrained URL model over lab URLs and realistic examples.

First run downloads the model (~15 MB) after torch/transformers are installed.
Usage:  python lab\\run_urlmodel.py
"""

from quishguard.urlmodel import url_phishing_score

LAB_URLS = [
    ("lab bank (legit)", "http://127.0.0.1:8000/"),
    ("lab phishing", "http://127.0.0.1:8001/"),
    ("lab collector", "http://127.0.0.1:8002/collect"),
]

# Clearly-benign vs obfuscated-looking strings, to show the model DOES work on
# real-world-shaped URLs (no real brands used).
REALISTIC_URLS = [
    ("well-known site", "huggingface.co/"),
    ("well-known site", "github.com/"),
    ("obfuscated host", "hu991ngface.com.ru/"),
    ("suspicious chain", "secure-login-verify.account-update.xyz/signin"),
]


def show(group: str, urls: list[tuple[str, str]]) -> None:
    print(f"\n{group}")
    for label, url in urls:
        p = url_phishing_score(url)
        verdict = "PHISH" if p >= 0.5 else "legit"
        print(f"  {verdict:5} p(phish)={p:0.3f}  [{label}] {url}")


if __name__ == "__main__":
    show("LAB URLs (all on 127.0.0.1 - the model has no signal here):", LAB_URLS)
    show("REALISTIC URLs (what the model was actually trained for):", REALISTIC_URLS)
