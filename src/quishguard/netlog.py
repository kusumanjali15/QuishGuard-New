"""Stage 5: record the requests a page makes."""

from dataclasses import dataclass
from urllib.parse import urlsplit


def origin_of(url: str) -> str:
    """Return the origin of a URL: scheme://host[:port].

    "http://127.0.0.1:8002/collect?x=1" -> "http://127.0.0.1:8002"
    """
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


@dataclass(frozen=True)
class RequestRecord:
    """One request the page started (what a network-layer defence can see)."""

    method: str          # GET, POST, ...
    url: str             # full destination URL
    resource_type: str   # document, fetch, xhr, image, ping, ...
    body: str | None     # POST body; None if there is none

    @property
    def destination(self) -> str:
        """The origin the request goes to."""
        return origin_of(self.url)


def record_from_playwright(request) -> RequestRecord:
    """Copy the parts we care about out of a Playwright Request object."""
    return RequestRecord(
        method=request.method,
        url=request.url,
        resource_type=request.resource_type,
        body=request.post_data,
    )
