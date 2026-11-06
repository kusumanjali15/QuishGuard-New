"""Stage 6: does a request carry something the user typed into a sensitive field?"""

from urllib.parse import unquote_plus

from quishguard.netlog import RequestRecord

# Typed values shorter than this are ignored: "1" or "ab" would match almost
# any URL (false positives). OTPs are 6 digits, passwords are longer.
MIN_LENGTH = 4


def _decoded_parts(record: RequestRecord) -> list[str]:
    """The URL and body of a request, URL-decoded (%40 -> @, + -> space)."""
    parts = [unquote_plus(record.url)]
    if record.body:
        parts.append(unquote_plus(record.body))
    return parts


def carries_sensitive(record: RequestRecord, typed_values: list[str]) -> bool:
    """True if any typed sensitive value appears in the request's URL or body.

    Catches plain and URL-encoded copies only - not values the page
    transforms before sending (see Stage 10 for the in-page sensor).
    """
    values = [v for v in typed_values if len(v) >= MIN_LENGTH]
    parts = _decoded_parts(record)
    return any(value in part for value in values for part in parts)
