"""Stage 3: create QR images for the lab sites (lab/qr/*.png)."""

from pathlib import Path

from quishguard.qr import decode_qr, make_qr

QR_DIR = Path(__file__).with_name("qr")
LAB_URLS = {
    "bank": "http://127.0.0.1:8000/",   # official Formosa Demo Bank
    "phish": "http://127.0.0.1:8001/",  # lab phishing copy
}

for name, url in LAB_URLS.items():
    path = make_qr(url, QR_DIR / f"{name}.png")
    print(f"{name:6} -> {path.name}   decodes to: {decode_qr(path)}")
