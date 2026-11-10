"""Stage 13: feature-set construction (no network / sklearn needed)."""

from quishguard.urlbaseline import CONTENT_FEATURES, EXTERNAL_FEATURES, feature_sets


def test_url_only_excludes_content_and_external() -> None:
    cols = ["url", "length_url", "nb_dots"] + CONTENT_FEATURES + EXTERNAL_FEATURES + ["status"]
    fs = feature_sets(cols)
    assert fs["url_only (56)"] == ["length_url", "nb_dots"]
    assert set(fs["all (87)"]) == {"length_url", "nb_dots", *CONTENT_FEATURES, *EXTERNAL_FEATURES}
    assert "page_rank" in fs["all (87)"] and "page_rank" not in fs["url+content (80)"]
