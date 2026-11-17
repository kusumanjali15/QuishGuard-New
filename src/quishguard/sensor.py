"""Stage 10: the Python side of the in-page sensor.

sensor.js holds a send and calls window.__qg_decide(send); Playwright routes that
call here. We reuse the Guard (rules + containment) to answer "allow" or "block".
"""

from pathlib import Path

from quishguard.guard import Guard
from quishguard.netlog import RequestRecord
from quishguard.rules import PageInfo
from quishguard.sensitive import MIN_LENGTH

SENSOR_JS = Path(__file__).with_name("sensor.js")


def judge_held_send(guard: Guard, send: dict) -> str:
    """Judge one send held by sensor.js. Returns "allow" or "block"."""
    observed = [v for v in send.get("typed", []) if v]  # OBSERVED in the page, not told
    guard.observed.update(observed)                     # share with the network layer
    guard.typed_values = list(observed)
    guard.page = PageInfo(send["pageUrl"], send["title"])
    rec = RequestRecord(send["method"], send["url"], send["channel"], send.get("body"))

    guard.log.append(f"HELD  [{rec.resource_type}] {rec.method} {rec.url}")
    decision = "block" if guard.decide(rec) == "abort" else "allow"
    guard.log.append("  -> dropped" if decision == "block" else "  -> released")
    return decision


def observe_values(guard: Guard, values: list[str]) -> None:
    """Record values seen typed into sensitive fields so the network layer can
    catch sends the sensor does not wrap. Ignore too-short values (same minimum
    as matching), so a 1-2 char field cannot pollute the observed set."""
    guard.observed.update(v for v in values if v and len(v) >= MIN_LENGTH)


async def install_sensor(context, guard: Guard) -> None:
    """Inject sensor.js into every page of a Playwright browser context."""
    await context.expose_function("__qg_decide", lambda send: judge_held_send(guard, send))
    await context.expose_function("__qg_observe", lambda values: observe_values(guard, values))
    await context.add_init_script(path=str(SENSOR_JS))
