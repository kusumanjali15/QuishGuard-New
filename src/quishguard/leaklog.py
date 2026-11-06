"""Write what attacker servers receive to a log, one JSON object per line."""

import json
from pathlib import Path
from typing import Any


def append_log_entry(log_path: Path, entry: dict[str, Any]) -> None:
    """Add one entry to the end of the log file, as a single JSON line.

    - Creates the folder (e.g. logs/) if it does not exist yet.
    - Never overwrites earlier entries.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
