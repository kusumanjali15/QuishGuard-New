
# Stage 14b — results (2026-11-28)

Live-behaviour lab, DynaPD kits, fully-isolated (network-disconnected) harness.

## Sample
- 301 kits sampled (first 301 by md5 from processed_kits_130323; 7,980 total). No selection by behaviour/brand.
- 278 produced a trace; 23 timed out at 45 s with no trace (counted as not-driven).

## Drivability (RQ3 denominator, stated honestly)
- Driven to a credential send: 101/301 = 33.6% (pilot of 51 gave ~31% — stable).
- The 200 non-driven: 129 front-end needs an external origin (served from live infra, dead offline);
  39 no form offline (server-gated or external-JS login); 9 form present but no credential POST; 23 timeout/no-trace.
- Offline-dead by construction = 168/301 (56%). This is a property of a fully-isolated harness, reported as a result, not hidden.

## Credential channel of the 101 driven kits
- 99/101 same-origin POST (sensor-coverable; a destination-only native check sees a benign-looking same-origin request).
- 2/101 client-side cross-origin send (the only kits whose send a destination-only native layer could flag on its own).
- 33/101 also triggered server-side mail exfil (captured by the sinkhole).
- Elicitation: 59/101 via the kit's own submit control; 42/101 via forced form-submit (flagged; the form action is same-origin POST either way, but we did not rely on the kit firing it).

## RQ3 reading
- Among observable kits, a destination-only native layer alone would see a benign same-origin request in 99/101 (~98%);
  the in-page sensor covers the credential send. Supports the two-layer argument on real kits.
- Android feasibility: WebView shouldInterceptRequest sees destination only, not the body — exactly the 99 same-origin cases where destination alone is insufficient.

## Selection bias (stated up front)
- The observable subset is self-contained, same-origin kits. Externally-dependent and JS-SPA kits are not observable offline and may behave differently.
- Larger N tightens the RQ3 coverage estimate but adds little behavioural diversity, so Stage 15 is a supporting result, not a headline.
