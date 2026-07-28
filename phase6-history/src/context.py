STATIC_CONTEXT = """\
Project: Mobile App Redesign.
Meeting type: this is one of a series of fifteen meetings between the two \
people in this transcript, referred to as Person A and Person B, spanning \
the project's full lifecycle from kickoff through launch retro over \
roughly five months — kickoff, requirements review, design review, seven \
sprint status syncs, test plan review, UAT kickoff, UAT results/triage, \
go-live readiness, and launch retro. Each meeting is a different type with \
its own purpose, not a repeated weekly status format.
Known workstreams for this release: rebuilding the onboarding flow, \
integrating a new payments provider, a visual refresh with dark mode, \
legal/privacy review, analytics instrumentation, and (raised early, cut \
from this release's scope) a localization request.
Purpose of this specific meeting: whatever that meeting type's own purpose \
is (e.g. a sprint sync checks workstream status, a design review approves \
mockups, UAT triage reviews bugs found in testing) — infer it from the \
transcript and the meeting history below, not from a fixed weekly agenda.\
"""


def build_history_block(history_entries):
    """Turn prior meetings' recorded outcomes into a block of text a later
    meeting's summarizer can use to correctly interpret callbacks like
    "the issue we flagged last week" instead of treating them as new,
    unexplained information."""
    if not history_entries:
        return "No prior meetings yet — this is the first one."
    lines = ["History of prior meetings so far, most recent last:"]
    lines.extend(history_entries)
    return "\n".join(lines)
