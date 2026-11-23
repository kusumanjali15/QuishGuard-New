"""Stage 8: network-layer guard - hold each request, then allow or block it.

Android note: shouldInterceptRequest can block by DESTINATION (so containment
works), but it cannot read POST bodies, so the "carries typed data?" check must
come from the in-page sensor there (Stage 10). To be verified in Stage 16.
"""

import time
from dataclasses import dataclass, field

from quishguard.netlog import RequestRecord, record_from_playwright
from quishguard.rules import PageInfo, ScanContext, score_send
from quishguard.sensitive import carries_sensitive


@dataclass
class Guard:
    scan: ScanContext
    typed_values: list[str] = field(default_factory=list)  # Stage 8: told; Stage 10: observed
    observed: set[str] = field(default_factory=set)  # Stage 12b: sensor-observed values, shared across layers
    page: PageInfo | None = None   # the page currently open
    contained: bool = False        # one-way switch: True after the first block
    log: list[str] = field(default_factory=list)
    deadline: float | None = None  # Stage 12b config (b): stop watching after this monotonic time
    loaded_at: float | None = None  # Stage 12b: page-load time (set by the harness), for timing
    blocked_at: float | None = None  # Stage 12b: monotonic time of the first block

    def decide(self, rec: RequestRecord) -> str:
        """Return "continue" or "abort" for one request."""
        if self.contained:
            self.log.append(f"BLOCK (contained)  {rec.method} {rec.url}")
            if self.blocked_at is None:
                self.blocked_at = time.monotonic()
            return "abort"

        if self.deadline is not None and time.monotonic() >= self.deadline:
            self.log.append(f"WINDOW-EXPIRED allow  {rec.method} {rec.url}")
            return "continue"

        values = self.typed_values + sorted(self.observed)
        if self.page and carries_sensitive(rec, values):
            verdict = score_send(self.page, rec.url, self.scan)
            if verdict.decision == "block":
                self.contained = True
                if self.blocked_at is None:
                    self.blocked_at = time.monotonic()
                self.log.append(f"BLOCK score={verdict.score}  {rec.method} {rec.url}")
                self.log.extend(f"      {reason}" for reason in verdict.reasons)
                return "abort"
            self.log.append(f"ALLOW sensitive send, score={verdict.score}  {rec.method} {rec.url}")

        return "continue"

    async def handle(self, route, request) -> None:
        """Playwright route handler: apply decide() to a held request."""
        if self.decide(record_from_playwright(request)) == "abort":
            await route.abort("blockedbyclient")
        else:
            await route.continue_()
