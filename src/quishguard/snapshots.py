"""Stage 14: sample the phishing-snapshots dataset across ALL shards and dedup.

PASSIVE data: each row is one headless-Chromium capture (HTML source, extracted
text, parsed form/input/script features, HAR). No typing, no interaction - so we
measure characteristics AT CAPTURE (post-initial-render, unknown delay), never
credential-send behaviour, and never strictly "at load".
"""

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pandas as pd

DATASET = "nyuuzyou/phishing-snapshots"
N_SHARDS = 28
SHARD_FMT = "data/train-{:05d}-of-00028.parquet"

# Only the columns Stage 14 needs. The big HAR column (`network_requests`) and
# other unused columns are SKIPPED to cut the download. Note: network-request
# domains live inside that HAR column, so for CAPTCHA/#2 we rely on
# external_script_urls / iframe_srcs / external_domains instead.
# LIGHT columns: everything the detectors need EXCEPT the two large blobs
# (`html`, `inline_scripts`). Note `inline_scripts_count` / `_total_bytes` are the
# cheap integer columns used by #4 - not the JS text itself.
SELECTED_COLUMNS = [
    "id", "domain", "final_url", "scan_timestamp", "title", "extracted_text",
    "text_length", "http_status", "has_html", "has_password_field", "input_fields",
    "input_count", "form_count", "form_actions", "external_script_urls",
    "iframe_srcs", "external_domains", "inline_scripts_count",
    "inline_scripts_total_bytes",
]
# HEAVY blobs: only for exact dedup, parse-verification, and the OC2 inline-JS
# search. Fetched as a small first-pages sample (see load_heavy_sample).
# HEAVY blobs + the light structural columns needed to run loose dedup on the
# same rows (title/input_fields/counts are tiny; they barely add to the download).
HEAVY_COLUMNS = ["id", "html", "inline_scripts", "title", "input_fields",
                 "input_count", "form_count"]
_WS = re.compile(r"\s+")


def _s(v) -> str:
    """Coerce a cell to a plain string ('' for None/NaN)."""
    if v is None:
        return ""
    try:
        if isinstance(v, float) and pd.isna(v):
            return ""
    except Exception:
        pass
    return str(v)


def _as_list(v) -> list:
    """Coerce a list/array/None cell to a Python list (numpy arrays included)."""
    if v is None:
        return []
    try:
        return list(v)
    except TypeError:
        return []


def _even_indices(num: int, k: int) -> list[int]:
    """k evenly spaced indices across range(num) - to spread across a shard's
    time-ordered row groups instead of taking only the earliest rows."""
    if k >= num:
        return list(range(num))
    step = num / k
    return sorted({int(i * step) for i in range(k)})


def _shard_path(i: int) -> str:
    return f"datasets/{DATASET}/{SHARD_FMT.format(i)}"


def _first_rows_with(i: int, columns: list[str], k: int) -> pd.DataFrame:
    """First k rows of shard i for the given columns, via iter_batches - reads only
    the first parquet PAGES, so pulling a few heavy-blob rows stays cheap. These are
    the EARLIEST rows of the shard (time-biased): use for parser checks / OC2 proxy /
    manual labelling, never for prevalence."""
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    fs = HfFileSystem()
    with fs.open(_shard_path(i)) as f:
        for batch in pq.ParquetFile(f).iter_batches(batch_size=k, columns=columns):
            return batch.to_pandas()
    return pd.DataFrame(columns=columns)


def load_heavy_sample(k_per_shard: int = 4, columns: list[str] | None = None,
                      shards: list[int] | None = None) -> pd.DataFrame:
    """Small sample WITH the heavy blobs (html, inline_scripts): first k rows of
    every shard. Time-biased by design; for exact dedup / OC2 / parse checks /
    manual labels only."""
    columns = HEAVY_COLUMNS if columns is None else columns
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    return pd.concat([_first_rows_with(i, columns, k_per_shard) for i in shards],
                     ignore_index=True)


def _read_selected(i: int, columns: list[str], rgroups_per_shard: int = 4) -> pd.DataFrame:
    """Read `rgroups_per_shard` evenly-spaced row groups of shard i, only the
    given columns - a targeted range read, not a whole-shard download."""
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    fs = HfFileSystem()
    with fs.open(_shard_path(i)) as f:
        pf = pq.ParquetFile(f)
        idx = _even_indices(pf.num_row_groups, min(rgroups_per_shard, pf.num_row_groups))
        table = pf.read_row_groups(idx, columns=columns)
    return table.to_pandas()


def load_sample(n: int | None = None, seed: int = 42, columns: list[str] | None = None,
                shards: list[int] | None = None) -> pd.DataFrame:
    """Load the LIGHT columns from every shard. n=None (default) returns ALL rows
    (~25 MB, exact prevalence); n=<int> returns a seeded ~n-row sample per shard.
    (Each shard is one row group, so sampling does not reduce the download.)"""
    columns = SELECTED_COLUMNS if columns is None else columns
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    per = None if n is None else max(1, round(n / len(shards)))
    parts = []
    for i in shards:
        df = _read_selected(i, columns)  # one row group -> all rows of the shard
        parts.append(df if per is None else df.sample(n=min(per, len(df)), random_state=seed + i))
    return pd.concat(parts, ignore_index=True)


def estimate_download(columns: list[str] | None = None, rgroups_per_shard: int = 4,
                      shards: list[int] | None = None) -> dict:
    """Read only the parquet FOOTERS (metadata, no row data) and report the
    expected download for load_sample: selected-columns vs all-columns bytes for
    the row groups we'd read. Cheap - call this BEFORE the real sample."""
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    columns = SELECTED_COLUMNS if columns is None else columns
    colset = set(columns)
    fs = HfFileSystem()
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    sel = all_ = rows = 0
    per_col: dict[str, int] = {}
    for i in shards:
        with fs.open(_shard_path(i)) as f:
            md = pq.ParquetFile(f).metadata
        for g in range(md.num_row_groups):
            rgm = md.row_group(g)
            rows += rgm.num_rows
            for c in range(rgm.num_columns):
                col = rgm.column(c)
                name = col.path_in_schema.split(".")[0]
                sz = col.total_compressed_size
                per_col[name] = per_col.get(name, 0) + sz
                all_ += sz
                if name in colset:
                    sel += sz
    top = sorted(per_col.items(), key=lambda kv: -kv[1])[:12]
    return {
        "selected_download_mb": round(sel / 1e6, 1),
        "all_columns_mb": round(all_ / 1e6, 1),
        "rows_total": rows,
        "per_column_mb_top12": {k: round(v / 1e6, 1) for k, v in top},
    }


def shard_time_ranges(shards: list[int] | None = None) -> pd.DataFrame:
    """Min/max scan_timestamp per shard (reads only that column - cheap). Lets you
    see whether shards are time-ordered before any big read."""
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    fs = HfFileSystem()
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    rows = []
    for i in shards:
        with fs.open(_shard_path(i)) as f:
            ts = pq.read_table(f, columns=["scan_timestamp"]).to_pandas()["scan_timestamp"]
        rows.append({"shard": i, "min_ts": ts.min(), "max_ts": ts.max(), "rows": len(ts)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- dedup keys
def normalized_html_hash(html: str | None) -> str:
    """EXACT-ish key: lowercase + collapse whitespace, then md5. Only identical
    markup merges; kits with per-victim tokens look different -> a LOWER bound on
    duplication (over-counts distinct pages)."""
    if not isinstance(html, str) or not html:
        return ""
    return hashlib.md5(_WS.sub(" ", html.lower()).strip().encode("utf-8", "ignore")).hexdigest()


def structural_key(row) -> str:
    """LOOSE key: title + sorted (input type|name) + input/form counts. Ignores
    per-victim tokens and the domain, so the same kit on many hosts merges. May
    over-merge genuinely different pages that share a layout."""
    title = _WS.sub(" ", _s(row.get("title")).lower()).strip()
    inputs = _as_list(row.get("input_fields"))
    sig = sorted(f"{_s(f.get('type')).lower()}|{_s(f.get('name')).lower()}" for f in inputs)
    blob = f"{title}||{','.join(sig)}||in={row.get('input_count')}||fm={row.get('form_count')}"
    return hashlib.md5(blob.encode("utf-8", "ignore")).hexdigest()


def _dedup_keys(df: pd.DataFrame, how: str) -> pd.Series:
    if how == "exact":
        return df["html"].map(normalized_html_hash)
    # loose: build keys over columns directly (far faster than df.apply(axis=1))
    cols = {c: df[c].tolist() for c in ("title", "input_fields", "input_count", "form_count")}
    keys = [structural_key({"title": ti, "input_fields": inf, "input_count": ic, "form_count": fc})
            for ti, inf, ic, fc in zip(cols["title"], cols["input_fields"],
                                       cols["input_count"], cols["form_count"])]
    return pd.Series(keys, index=df.index)


def dedup(df: pd.DataFrame, how: str = "exact") -> pd.DataFrame:
    """Keep the first row per dedup key. how = 'none' | 'exact' | 'loose'."""
    if how == "none":
        return df.copy()
    if how not in ("exact", "loose"):
        raise ValueError(f"unknown how: {how}")
    return df.loc[~_dedup_keys(df, how).duplicated()].copy()


def dedup_counts(df: pd.DataFrame) -> dict[str, int]:
    """Row counts under each dedup level (none / exact / loose)."""
    out = {"none": len(df), "loose": len(dedup(df, "loose"))}
    if "html" in df.columns:
        out["exact"] = len(dedup(df, "exact"))
    return out


# ---------------------------------------------------- verify pre-parsed columns
class _InputCounter(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.count = 0
        self.has_pw = False

    def handle_starttag(self, tag, attrs) -> None:
        if tag.lower() == "input":
            self.count += 1
            if (dict(attrs).get("type") or "").lower() == "password":
                self.has_pw = True


def parse_inputs(html: str | None) -> tuple[int, bool]:
    """Our own count of <input> elements and whether any is type=password."""
    p = _InputCounter()
    try:
        p.feed(html if isinstance(html, str) else "")
    except Exception:
        pass
    return p.count, p.has_pw


def verify_parsed_columns(n: int = 30, seed: int = 42, shard: int = 0) -> pd.DataFrame:
    """Compare the dataset's has_password_field / input_count with OUR parse of
    the html column, on n rows from one shard. Any mismatch hints at raw-vs-render
    differences or parser quirks."""
    df = _first_rows_with(shard, ["id", "html", "input_count", "has_password_field"], n * 3)
    sample = df.sample(n=min(n, len(df)), random_state=seed)
    rows = []
    for _, r in sample.iterrows():
        our_count, our_pw = parse_inputs(r["html"])
        theirs = int(r["input_count"] or 0)
        rows.append({
            "id": r["id"], "their_inputs": theirs, "our_inputs": our_count,
            "their_pw": bool(r["has_password_field"]), "our_pw": our_pw,
            "input_mismatch": theirs != our_count,
            "pw_mismatch": bool(r["has_password_field"]) != our_pw,
        })
    return pd.DataFrame(rows)


def export_label_set(path, n: int = 100, seed: int = 7, df: pd.DataFrame | None = None):
    """Write a random n-row label sheet (CSV, Excel/zh-TW friendly): context columns
    + each detector's flag + an empty truth:: column to fill with 1/0. For the
    manual-precision step (14.5). Uses the LIGHT columns (title/text/structure)."""
    from quishguard.detectors import LIGHT_DETECTORS
    if df is None:
        df = load_sample()
    s = df.sample(n=min(n, len(df)), random_state=seed).reset_index(drop=True)
    txt = s["extracted_text"].fillna("").astype(str).str.replace(r"\s+", " ", regex=True)
    out = pd.DataFrame({
        "id": s["id"], "domain": s["domain"], "url": s.get("final_url"),
        "title": s["title"].fillna("").astype(str).str.slice(0, 200),
        "text": txt.str.slice(0, 1200),
        "text_length": s["text_length"], "has_password_field": s["has_password_field"],
        "input_count": s["input_count"], "form_count": s["form_count"],
        "inline_scripts_bytes": s["inline_scripts_total_bytes"],
    })
    from quishguard.detectors import row_evidence
    for name, fn in LIGHT_DETECTORS.items():
        flags = fn(s).astype(int).values
        out[f"flag::{name}"] = flags
        out[f"evidence::{name}"] = [row_evidence(s.iloc[i], name) if flags[i] else "" for i in range(len(s))]
        out[f"truth::{name}"] = ""          # fill 1 (really is) / 0 (false flag)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path, len(out)


def export_supplement(path, detectors=("2a_captcha_widget", "2b_cloudflare_interstitial",
                                       "3_non_credential_lure", "4_script_driven"),
                      per: int = 20, seed: int = 11, df: pd.DataFrame | None = None):
    """Flagged-stratified sheet: up to `per` FLAGGED rows for each rare detector,
    with evidence and a single truth column. For precision on detectors too rare
    in a 100-row random sample."""
    from quishguard.detectors import LIGHT_DETECTORS, row_evidence
    if df is None:
        df = load_sample()
    rows = []
    for name in detectors:
        flagged = df[LIGHT_DETECTORS[name](df)]
        samp = flagged.sample(n=min(per, len(flagged)), random_state=seed)
        for _, r in samp.iterrows():
            rows.append({
                "detector": name, "id": r["id"], "domain": r["domain"], "url": r.get("final_url"),
                "title": _s(r.get("title"))[:200],
                "text": re.sub(r"\s+", " ", _s(r.get("extracted_text")))[:1200],
                "text_length": r.get("text_length"),
                "has_password_field": r.get("has_password_field"),
                "input_count": r.get("input_count"), "form_count": r.get("form_count"),
                "inline_scripts_bytes": r.get("inline_scripts_total_bytes"),
                "evidence": row_evidence(r, name), "flag": 1, "truth": "",
            })
    out = pd.DataFrame(rows)
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path, len(out)


def supplement_precision(path):
    from quishguard.detectors import wilson_ci
    df = pd.read_csv(path)
    rows = []
    for name, g in df.groupby("detector"):
        lab = g[pd.to_numeric(g["truth"], errors="coerce").isin([0, 1])]
        n = len(lab)
        k = int((pd.to_numeric(lab["truth"], errors="coerce") == 1).sum()) if n else 0
        lo, hi = wilson_ci(k, n)
        rows.append({"detector": name, "flagged_labeled": n,
                     "precision_%": round(100 * k / n, 1) if n else None,
                     "95ci": f"{round(100*lo,1)}-{round(100*hi,1)}" if n else "n/a"})
    return pd.DataFrame(rows)


def heavy_estimate(k_per_shard: int = 36, shards: list[int] | None = None) -> dict:
    """Footer-based estimate of the heavy (html+inline_scripts) download for
    k_per_shard rows/shard. Lower bound - iter_batches reads whole pages, so the
    real pull is somewhat larger."""
    from huggingface_hub import HfFileSystem
    import pyarrow.parquet as pq

    fs = HfFileSystem()
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    heavy = {"html", "inline_scripts"}
    est = 0.0
    for i in shards:
        with fs.open(_shard_path(i)) as f:
            md = pq.ParquetFile(f).metadata
        rg = md.row_group(0)
        frac = min(1.0, k_per_shard / rg.num_rows)
        for c in range(rg.num_columns):
            col = rg.column(c)
            if col.path_in_schema.split(".")[0] in heavy:
                est += col.total_compressed_size * frac
    return {"rows": k_per_shard * len(shards), "k_per_shard": k_per_shard,
            "approx_download_mb_lower_bound": round(est / 1e6, 1)}


def label_precision(path):
    """Read a labelled sheet and report each detector's precision (of flagged rows,
    how many truth==1) with a Wilson 95% CI."""
    from quishguard.detectors import wilson_ci
    df = pd.read_csv(path)
    rows = []
    for col in [c for c in df.columns if c.startswith("flag::")]:
        name = col.split("::", 1)[1]
        tcol = f"truth::{name}"
        if tcol not in df.columns:
            continue
        flagged = df[df[col] == 1]
        labeled = flagged[pd.to_numeric(flagged[tcol], errors="coerce").isin([0, 1])]
        n = len(labeled)
        k = int((pd.to_numeric(labeled[tcol], errors="coerce") == 1).sum()) if n else 0
        lo, hi = wilson_ci(k, n)
        rows.append({"detector": name, "flagged_labeled": n,
                     "precision_%": round(100 * k / n, 1) if n else None,
                     "95ci": f"{round(100*lo,1)}-{round(100*hi,1)}" if n else "n/a"})
    return pd.DataFrame(rows)

URL_COLUMNS = ["id", "url", "final_url", "domain", "redirect_chain", "http_status",
               "has_password_field"]


def export_url_dataset(path, df: pd.DataFrame | None = None):
    """Write the phishing URLs + cheap URL features to a CSV you can open/show.
    Phishing-only (no benign) - descriptive, or a base to pair with a benign set."""
    import ipaddress
    from urllib.parse import urlsplit
    from quishguard.detectors import _reg_domain

    if df is None:
        df = pd.concat([_read_selected(i, URL_COLUMNS) for i in range(N_SHARDS)],
                       ignore_index=True)

    def host_of(u):
        return urlsplit(_s(u)).netloc.split("@")[-1].split(":")[0].lower()

    def is_ip(h):
        try:
            ipaddress.ip_address(h)
            return True
        except ValueError:
            return False

    urls = df["url"].map(_s)
    hosts = urls.map(host_of)
    out = pd.DataFrame({
        "id": df["id"], "url": urls, "final_url": df["final_url"], "domain": df["domain"],
        "http_status": df["http_status"], "has_password_field": df["has_password_field"],
        "url_length": urls.map(len),
        "host": hosts,
        "registrable_domain": urls.map(lambda u: _reg_domain(_s(u))),
        "is_https": urls.map(lambda u: _s(u).lower().startswith("https://")),
        "has_ip_host": hosts.map(is_ip),
        "has_at": urls.map(lambda u: "@" in _s(u)),
        "subdomain_depth": hosts.map(lambda h: max(0, h.count(".") - 1)),
        "path_depth": urls.map(lambda u: urlsplit(_s(u)).path.strip("/").count("/") + 1 if urlsplit(_s(u)).path.strip("/") else 0),
        "num_digits": urls.map(lambda u: sum(c.isdigit() for c in _s(u))),
        "redirect_count": df["redirect_chain"].map(lambda c: len(_as_list(c))),
    })
    out.to_csv(path, index=False, encoding="utf-8-sig")
    return path, len(out)

def load_label_pool(first_rows_per_shard: int = 300, shards: list[int] | None = None) -> pd.DataFrame:
    """First-pages pool that ALSO carries `html` (for offline screenshot rendering)
    plus every column the detectors need. Downloads ~first_rows_per_shard*28 rows of
    html (a few hundred MB at 300) - earliest rows per shard (time-biased)."""
    cols = SELECTED_COLUMNS + ["html"]
    shards = list(range(N_SHARDS)) if shards is None else list(shards)
    return pd.concat([_first_rows_with(i, cols, first_rows_per_shard) for i in shards],
                     ignore_index=True)


def input_summary(cell) -> str:
    """input_fields -> 'type:name:placeholder | ...' (first 8)."""
    out = [f"{_s(f.get('type'))}:{_s(f.get('name'))}:{_s(f.get('placeholder'))}"
           for f in _as_list(cell)]
    return " | ".join(out[:8])

