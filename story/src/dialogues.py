# Five weekly status syncs for the same Mobile App Redesign project (same
# premise as v1-v4), telling one continuous story instead of a single
# snapshot meeting. Each week's dialogue deliberately references earlier
# weeks by name ("the sandbox issue from week one", "the extra engineer we
# talked about last week") so that a summarizer without access to prior
# meetings can only paraphrase what's said out loud, while one with a running
# history can correctly explain *why* something is being brought up again.
#
# Throughline across the 5 weeks:
#   - Payments sandbox: flagged flaky (W1) -> worse, blocking QA (W2) ->
#     still unresolved, now 3 weeks running (W3) -> vendor fixes it (W4)
#   - Dark mode: not started (W1) -> picked up as bonus (W2) -> shipped (W3)
#   - Legal/privacy: kicked off (W1) -> reviewing (W2) -> still reviewing (W3)
#     -> approved (W4)
#   - Analytics: scoped (W1) -> chased again (W2) -> engineer requested (W3)
#     -> wired up, validating (W4) -> validated (W5)
#   - Budget / cost impact: never discussed on any call, called out explicitly
#     in week 5 (mirrors the deliberate checklist gap in v1-v4)
#
# Each meeting also opens with a few lines of clearly non-project small talk
# (weather, a TV series, a game, coffee, pre-review nerves) — distinct
# per-week words chosen not to collide with any real project vocabulary
# elsewhere in these scripts, so a summarizer's success at excluding them
# from Topic/Key Points/Decisions/Actions can be checked with a plain
# keyword match (see eval/story_probes.py's NOISE_KEYWORDS).

SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

MEETINGS = [
    {
        "week": 1,
        "label": "Week 1",
        "intro": (
            "You are about to hear the first of five weekly status sync recordings "
            "about the mobile app redesign project, roughly four weeks before the "
            "stakeholder review."
        ),
        "dialogue": [
            ("A", "Hey, before we get started, how's your week been?"),
            ("B", "Not bad, thanks. Pretty gray and rainy here all week though."),
            ("A", "Same here, I heard the weather's supposed to clear up by the weekend at least."),
            ("B", "Fingers crossed, perfect excuse to finally start that new series everyone's been talking about."),
            ("A", "Oh, I've heard good things, let me know how the first episode is."),
            ("B", "Will do. Anyway, ready to dive in?"),
            ("A", "Yep, let's get into it. Thanks for hopping on, this is our first sync on the mobile app redesign. We've got about four weeks until the stakeholder review, so let's use these Monday calls to track status."),
            ("B", "Sounds good. Quick rundown: the onboarding flow is built, we're kicking off user testing this week. Payments integration with the new provider just started, we're standing up their sandbox environment now."),
            ("A", "Any concerns already?"),
            ("B", "The sandbox felt a little flaky in our first smoke tests yesterday. Nothing alarming yet, but worth watching."),
            ("A", "Let's keep an eye on it. What about the visual refresh?"),
            ("B", "Design hasn't started on that yet, it's a stretch goal if we have bandwidth after the core work."),
            ("A", "Understood. I'll get legal looped in this week so privacy review isn't a bottleneck later, and I'll ask analytics to scope what events we need for the new flow."),
            ("B", "Sounds like a plan. I'll keep monitoring the sandbox and flag it immediately if it gets worse."),
            ("A", "Perfect, let's regroup same time next Monday."),
            ("B", "Talk then."),
        ],
    },
    {
        "week": 2,
        "label": "Week 2",
        "intro": "This is the second weekly status sync recording about the mobile app redesign project.",
        "dialogue": [
            ("A", "Morning, how was your weekend?"),
            ("B", "Pretty relaxed, actually. Just caught up on sleep and finally started that series I mentioned."),
            ("A", "Oh nice, how's the first episode?"),
            ("B", "Really good so far, no spoilers though, I know you want to watch it too."),
            ("A", "Ha, deal. Alright, let's jump into status. Week two check-in. Last week we flagged the payments sandbox as a little flaky, where does that stand?"),
            ("B", "It's gotten worse actually. The vendor's sandbox has been unstable most of this week, our QA team's been blocked more than they've been testing."),
            ("A", "That's a bigger deal than I expected. What's the plan?"),
            ("B", "If it's not stable by Thursday, I want to delay the payments sign-off rather than rush it through half-tested."),
            ("A", "Agreed, quality over the deadline on that one. How's onboarding testing going?"),
            ("B", "User testing is underway, we'll have results by early next week."),
            ("A", "And the dark mode stretch goal?"),
            ("B", "Actually one of our engineers picked it up this week since they had some slack time, it's in progress now."),
            ("A", "Nice bonus. I did loop in legal, they're starting their review of the privacy language for the permissions screen now."),
            ("B", "Good, that was fast. Anything from analytics?"),
            ("A", "Not yet, I'll chase them again, it's still a risk for the review if we don't have usage data ready."),
            ("B", "Okay, let's reconvene next Monday and see where the sandbox situation lands."),
        ],
    },
    {
        "week": 3,
        "label": "Week 3",
        "intro": "This is the third weekly status sync recording about the mobile app redesign project.",
        "dialogue": [
            ("A", "Hey, did you catch the game last night?"),
            ("B", "I did, what an ending, I was not expecting that."),
            ("A", "Same, I nearly spilled my coffee. Anyway, let's get into this week's update. Week three, two weeks out from the review now. How did onboarding testing land?"),
            ("B", "Great news there, we finished user testing with twelve participants and completion rate jumped from sixty to eighty eight percent."),
            ("A", "That's a huge improvement. And the sandbox issue we've been chasing since week one?"),
            ("B", "Still not resolved, honestly it's the same instability, now it's eaten into a second full week and QA has only run about half their test cases."),
            ("A", "That's frustrating. Are we still holding the line on not shipping it half-tested?"),
            ("B", "Yes, I'd still rather delay the payments sign-off than ship something shaky."),
            ("A", "Agreed. What about dark mode, the bonus item from last week?"),
            ("B", "Finished, actually, every screen has the variant now."),
            ("A", "Great initiative from the team. Where's legal on the privacy review?"),
            ("B", "Still reviewing, no answer yet, might be worth a nudge."),
            ("A", "I'll ping them today. Did analytics ever pick up the instrumentation request?"),
            ("B", "Not yet, we could really use another engineer to help with that and with the payments test backlog."),
            ("A", "I'll see who I can free up. Let's sync again next Monday."),
        ],
    },
    {
        "week": 4,
        "label": "Week 4",
        "intro": "This is the fourth weekly status sync recording about the mobile app redesign project.",
        "dialogue": [
            ("A", "Morning, new coffee place downstairs is dangerous, I've had three cups already."),
            ("B", "Ha, I noticed the line earlier. Worth it though?"),
            ("A", "Absolutely. Okay, let's get into it. Week four, one week from the review. Good news first, the sandbox issue that's been dragging since week one is finally fixed."),
            ("B", "Yes, the vendor pushed a patch Tuesday, QA's been able to run the full payments test suite since, and it's all passing so far."),
            ("A", "Excellent, that's a huge relief. What about legal, did they finally get back to us on the privacy language?"),
            ("B", "They did, it's approved, no changes needed."),
            ("A", "Great. Did the extra engineer we talked about help with analytics?"),
            ("B", "Yes, they got pulled in this week, the instrumentation is wired up now, just needs another day or two of validation before we fully trust the numbers."),
            ("A", "That should be plenty of time before next week. Onboarding and dark mode are both already done, so we're in decent shape overall."),
            ("B", "Agreed. I'll finish validating analytics and get you the numbers by Friday."),
            ("A", "Perfect, I'll start pulling the stakeholder deck together this week."),
            ("B", "Sounds good, talk next Monday, our last check-in before the review."),
        ],
    },
    {
        "week": 5,
        "label": "Week 5",
        "intro": "This is the fifth and final weekly status sync recording about the mobile app redesign project, the day before the stakeholder review.",
        "dialogue": [
            ("A", "Morning, big day tomorrow, you feeling ready?"),
            ("B", "As ready as we'll ever be. Slept surprisingly well actually, given the traffic to get here this morning."),
            ("A", "Ha, the traffic's been rough all week. Alright, let's do a final run-through. Final sync before Friday's review. Let's run through everything one more time. Onboarding?"),
            ("B", "Done, eighty eight percent completion rate, no open items."),
            ("A", "Payments, after that whole sandbox saga from the first few weeks?"),
            ("B", "Fully resolved and tested, the full suite's been green since the vendor's fix last week."),
            ("A", "Dark mode?"),
            ("B", "Shipped, every screen."),
            ("A", "Legal?"),
            ("B", "Approved a few weeks back already, nothing outstanding."),
            ("A", "Analytics, after pulling in that extra engineer?"),
            ("B", "Validated, the numbers look solid, I sent you the dashboard link this morning."),
            ("A", "Perfect, I think we're in great shape for Friday, I've got the stakeholder deck finished with all of this in it."),
            ("B", "One thing we still haven't touched across any of these calls is budget or cost impact for the new payments provider, might be worth flagging separately."),
            ("A", "Good catch, we'll pick that up outside this meeting so it doesn't hold up Friday."),
            ("B", "Sounds good. See you at the review."),
            ("A", "Talk then, thanks everyone."),
        ],
    },
]
