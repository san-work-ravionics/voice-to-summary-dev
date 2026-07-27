# Each checklist item pairs a topic with keywords used to detect whether
# it was actually discussed (see summarize.py for why this check is
# keyword-based rather than another LLM call).
CHECKLIST = [
    ("Onboarding flow status", ["onboarding"]),
    ("Payments integration status", ["payment"]),
    ("Design updates (e.g. dark mode)", ["dark mode"]),
    ("Legal / privacy approval", ["legal", "privacy"]),
    ("Analytics instrumentation", ["analytics"]),
    ("Budget or cost impact", ["budget", "cost impact", "cost of"]),
    ("Next meeting / follow-up schedule", ["follow-up", "follow up", "next meeting", "sync again", "set up the invite"]),
]
