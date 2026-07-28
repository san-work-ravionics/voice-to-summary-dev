"""Simulated network conditions for the office agent.

There's no real network-shaping infrastructure in this repo (no Network
Link Conditioner, no proxy), so "low network" is a documented simulation
rather than a real one: `degraded` injects latency plus one simulated
timeout+retry before the underlying Claude call goes out; `offline` never
calls Claude at all and raises Offline, which the caller (main.py) catches
to fall back to the local, on-device model — the one condition where a
cloud agent (Copilot Enterprise or its Claude stand-in here) structurally
can't help at all.
"""
import time

CONDITIONS = ("good", "degraded", "offline")

DEGRADED_LATENCY_S = 4.0
DEGRADED_RETRY_LATENCY_S = 6.0


class Offline(Exception):
    """Raised instead of making any call under condition='offline'."""


def wrap(condition):
    """Returns a network_call(fn) callable for office_agent.run_agent()."""
    if condition == "good":
        return lambda fn: fn()

    if condition == "degraded":
        def call(fn):
            time.sleep(DEGRADED_LATENCY_S)
            try:
                return fn()
            except Exception:
                # Simulated dropped request — one retry after a longer
                # delay, the way a real client backs off on a flaky link.
                time.sleep(DEGRADED_RETRY_LATENCY_S)
                return fn()
        return call

    if condition == "offline":
        def call(fn):
            raise Offline("Copilot unavailable (simulated offline) — falling back to on-device")
        return call

    raise ValueError(f"Unknown network condition {condition!r}; expected one of {CONDITIONS}")
