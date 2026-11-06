"""Stage 0 sanity check: proves pytest runs and our package can be imported."""

import quishguard

def test_version_is_set() -> None:
    """Proves pytest can import our package and read its version."""
    assert quishguard.__version__ == "0.0.1"