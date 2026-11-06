"""Stage 3: tests for make_qr / decode_qr."""

from pathlib import Path

import pytest
from PIL import Image

from quishguard.qr import decode_qr, make_qr


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/",  # official bank
        "http://127.0.0.1:8001/",  # phishing site
        "http://127.0.0.1:8001/login?ref=parcel&id=4821",  # query string survives
    ],
)
def test_round_trip(tmp_path: Path, url: str) -> None:
    image_path = make_qr(url, tmp_path / "code.png")
    assert decode_qr(image_path) == url


def test_image_without_qr_raises(tmp_path: Path) -> None:
    blank = tmp_path / "blank.png"
    Image.new("RGB", (200, 200), "white").save(blank)
    with pytest.raises(ValueError):
        decode_qr(blank)


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        decode_qr(tmp_path / "does_not_exist.png")
