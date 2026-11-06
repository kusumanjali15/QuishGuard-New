"""Make and read QR codes (Stage 3)."""

from pathlib import Path

import cv2
import qrcode


def make_qr(text: str, path: Path) -> Path:
    """Encode text (usually a URL) as a QR code and save it as a PNG."""
    path.parent.mkdir(parents=True, exist_ok=True)
    image = qrcode.make(text)  # default error correction: M (~15% damage tolerated)
    image.save(path)
    return path


def decode_qr(path: Path) -> str:
    """Read the text stored in the QR code inside an image file.

    Raises FileNotFoundError if the image cannot be opened,
    and ValueError if no readable QR code is found.
    """
    image = cv2.imread(str(path))  # returns None instead of raising on a bad file
    if image is None:
        raise FileNotFoundError(f"cannot open image: {path}")

    text, _corners, _grid = cv2.QRCodeDetector().detectAndDecode(image)
    if not text:  # OpenCV returns "" when it finds no QR code
        raise ValueError(f"no readable QR code in: {path}")
    return text
