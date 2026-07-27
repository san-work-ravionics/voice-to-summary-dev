STATIC_CONTEXT = """\
Project: Mobile App Redesign.
Meeting type: this is one of a series of five weekly Monday status syncs \
between the two people in this transcript, referred to as Person A and \
Person B, held in the weeks leading up to a stakeholder review.
Known workstreams for this release: onboarding flow, payments integration \
with a new provider, a visual refresh including a dark mode variant, \
legal/privacy approval for the permissions screen, and analytics \
instrumentation for the new flow.
Purpose of this specific meeting: check status across those workstreams, \
flag any risks to the upcoming review, and confirm what each person still \
needs to do before the next sync.\
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
