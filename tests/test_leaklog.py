"""Stage 2: tests for append_log_entry.

tmp_path is a pytest "fixture": pytest gives each test its own empty temporary
folder, so tests never touch the real logs/ folder.
"""

import json
from pathlib import Path

from quishguard.leaklog import append_log_entry


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_writes_one_json_line(tmp_path: Path) -> None:
    log = tmp_path / "attacker.log"
    entry = {"server": "collector", "fields": {"password": "Lab-Pass-4821"}}
    append_log_entry(log, entry)
    assert read_lines(log) == [entry]


def test_appends_instead_of_overwriting(tmp_path: Path) -> None:
    log = tmp_path / "attacker.log"
    append_log_entry(log, {"n": 1})
    append_log_entry(log, {"n": 2})
    assert read_lines(log) == [{"n": 1}, {"n": 2}]


def test_creates_missing_folders(tmp_path: Path) -> None:
    log = tmp_path / "logs" / "lab" / "attacker.log"   # folders don't exist yet
    append_log_entry(log, {"n": 1})
    assert log.exists()
