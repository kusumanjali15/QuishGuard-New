"""Scrub victim e-mail addresses out of the hand-labelled precision sheets.

Some captured phishing URLs, pre-filled input fields and page texts contain real
victims' e-mail addresses, in plain text or base64-encoded. Before the repo is
public, every copy of lab/labels.csv and lab/labels_supplement.csv must be scrubbed:
  - url column  -> scheme + host only (path and query dropped)
  - other cells -> plain e-mails and base64 tokens that decode to an e-mail are redacted
The detector flags and truth labels are untouched, so precision results do not change.

Usage:
  python lab\\scrub_labels.py           # scrub the files in place (no-op if already clean)
  python lab\\scrub_labels.py --check   # report what would change, write nothing
"""

import base64
import csv
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).parent
FILES = [HERE / "labels.csv", HERE / "labels_supplement.csv"]

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
B64_TOKEN = re.compile(r"[A-Za-z0-9+/_-]{12,}={0,2}")


def decodes_to_email(token: str) -> bool:
    """True if a base64 / base64url token decodes to text containing an e-mail."""
    s = token.replace("-", "+").replace("_", "/")
    s += "=" * (-len(s) % 4)
    try:
        return bool(EMAIL.search(base64.b64decode(s).decode("latin-1")))
    except Exception:
        return False


def scrub_cell(value: str) -> str:
    value = EMAIL.sub("[email-redacted]", value)
    return B64_TOKEN.sub(lambda m: "[b64-email-redacted]" if decodes_to_email(m.group()) else m.group(), value)


def scrub_url(value: str) -> str:
    """Keep only scheme://host/ - the path and query are where victim data hides."""
    if not value:
        return value
    parts = urlsplit(value)
    return f"{parts.scheme}://{parts.netloc}/" if parts.netloc else scrub_cell(value)


def scrub_file(path: Path, write: bool) -> int:
    """Scrub one CSV. Returns the number of cells changed."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = list(reader)

    changed = 0
    for row in rows:
        for col in fields:
            old = row[col] or ""
            new = scrub_url(old) if col == "url" else scrub_cell(old)
            if new != old:
                row[col] = new
                changed += 1

    if write and changed:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
    return changed


def main() -> None:
    write = "--check" not in sys.argv
    for path in FILES:
        if not path.exists():
            continue  # older commits do not have the label sheets yet
        n = scrub_file(path, write)
        print(f"{path.name}: {n} cells {'scrubbed' if write else 'would be scrubbed'}")


if __name__ == "__main__":
    main()
