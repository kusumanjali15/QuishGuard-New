"""Stage 8: network-layer guard - hold each request, then allow or block it.

Android note: shouldInterceptRequest can block by DESTINATION (so containment
works), but it cannot read POST bodies, so the "carries typed data?" check must
come from the in-page sensor there (Stage 10). To be verified in Stage 16.
"""

from dataclasses import dataclass, field

from quishguard.netlog import RequestRecord, record_from_playwright
from quishguard.rules import PageInfo, ScanContext, score_send
from quishguard.sensitive import carries_sensitive


@dataclass
class Guard:
    scan: ScanContext
    typed_values: list[str] = field(default_factory=list)  # Stage 8: told; Stage 10: observed
    page: PageInfo | None = None   # the page currently open
    contained: bool = False        # one-way switch: True after the first block
    log: list[str] = field(default_factory=list)

    def decide(self, rec: RequestRecord) -> str:
        """Return "continue" or "abort" for one request."""
        if self.contained:
            self.log.append(f"BLOCK (contained)  {rec.method} {rec.url}")
            return "abort"

        if self.page and carries_sensitive(rec, self.typed_values):
            verdict = score_send(self.page, rec.url, self.scan)
            if verdict.decision == "block":
                self.contained = True
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
