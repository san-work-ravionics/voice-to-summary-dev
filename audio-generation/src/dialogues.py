# Fifteen meetings covering the full lifecycle of the same Mobile App
# Redesign project used elsewhere in this repo (phase1-baseline through
# phase6-history) — kickoff through launch retro, roughly five months,
# instead of a single snapshot or a short run of weekly status syncs.
#
# Unlike a repeated weekly-status format, each meeting here
# is a distinct meeting TYPE (kickoff, requirements review, design review,
# sprint status x7, test plan review, UAT kickoff, UAT results/triage,
# go-live readiness, launch retro) with its own shape and purpose.
#
# Threads that run continuously across meetings so later ones only make
# sense with the ones before them:
#   - Payments integration (new vendor): scoped (01) -> P0 backlog (02) ->
#     sandbox provisioned (03) -> "a little flaky" (04) -> worse, blocking
#     QA (05) -> still broken, 3rd sprint (06), escalated to vendor -> vendor
#     engaged, fix ETA (07) -> patch shipped, passing (08) -> fully stable,
#     signed off (09) -> feature complete (10) -> in test plan scope (11) ->
#     in UAT scope (12) -> P1 edge-case bug found (13) -> fixed, retested,
#     GO (14) -> praised in retro as the big mid-project scare (15)
#   - Dark mode / visual refresh: raised as a stretch goal (01) -> P1
#     stretch in backlog (02) -> promoted to committed scope at design
#     review (03) -> not started (04) -> engineer starts early (05) ->
#     in progress (06) -> first screens shipped (07) -> fully shipped (08)
#     -> done (09-10) -> praised in retro (15)
#   - Legal/privacy: flagged as needed (01) -> engagement kicked off (02) ->
#     review starts (04) -> still reviewing (05) -> nudged, no answer (06)
#     -> responds with copy edits (07) -> approved (08)
#   - Analytics: scoped (01-02) -> chased, risk (05) -> extra engineer
#     requested (06) -> engineer pulled in, wired up (07) -> validating (08)
#     -> validated (09) -> post-launch dashboard live (15)
#   - Localization: raised as a nice-to-have by a stakeholder (01) ->
#     explicitly CUT from this release's scope (02) -> resurfaces as a UAT
#     tester question (12) -> formally logged as a future-release backlog
#     item, not an oversight (13) -> closed out in retro (15)
#   - Performance/load testing: first raised (08) -> test plan drafted (09)
#     -> finalized (10) -> executed with a scoped plan (11) -> results with
#     one caveat (13) -> caveat fixed, signed off (14)
#   - Budget/cost impact: never discussed until go-live readiness, where the
#     payments fire-drill's cost is flagged for the first time (14) -> only
#     then closed out in retro (15) — deliberately absent everywhere else,
#     the same kind of gap phase2-checklist/phase6-history use elsewhere.
#   - Support/Help-center readiness and marketing/launch comms: both first
#     appear at go-live readiness (14), resolved in retro (15).
#
# Each meeting also opens with a few lines of throwaway small talk, a
# distinct topic per meeting, worded not to collide with any project
# vocabulary — same pattern this project's meeting scripts always use.

SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

MEETINGS = [
    {
        "slug": "01-kickoff",
        "label": "Project Kickoff",
        "meeting_type": "kickoff",
        "intro": (
            "You are about to hear the first of fifteen recordings covering the "
            "mobile app redesign project from kickoff through launch, spanning "
            "roughly five months. This is the project kickoff."
        ),
        "dialogue": [
            ("A", "Hey, thanks for making time. Did you end up signing up for that half-marathon you mentioned?"),
            ("B", "I did, registration closed yesterday. Now I actually have to train for it."),
            ("A", "Ha, good luck with that. Alright, let's get started, this is our kickoff for the mobile app redesign."),
            ("B", "Excited for this one. What's the high-level goal?"),
            ("A", "Improve onboarding conversion and give the app a visual refresh, with a hard target of launching in about five months."),
            ("B", "Okay. What's the engineering scope look like?"),
            ("A", "Four workstreams: rebuilding the onboarding flow, integrating a new payments provider, the visual refresh with dark mode as a stretch goal, and we'll need legal and privacy review plus analytics instrumentation running alongside all of it."),
            ("B", "Payments is the one that worries me. New vendor means we don't know their sandbox is solid until we're in it. I want access on day one."),
            ("A", "Agreed, I'll push to get that provisioned this week. I'll also get legal engaged early so it's not a bottleneck later, and loop analytics in to start scoping events."),
            ("B", "Sounds good. One more thing, a stakeholder asked me if this includes other languages, is localization in scope?"),
            ("A", "Not decided yet. Let's bring that to requirements review next week and settle it there rather than assume."),
            ("B", "Fair enough."),
            ("A", "Great, let's reconvene next week for requirements review, then we'll settle into two-week sprint syncs after that."),
            ("B", "Sounds good, talk then."),
        ],
    },
    {
        "slug": "02-requirements-review",
        "label": "Requirements Review",
        "meeting_type": "requirements_review",
        "intro": "This is the requirements review meeting for the mobile app redesign project, one week after kickoff.",
        "dialogue": [
            ("A", "Morning. How was the flight back from your trip?"),
            ("B", "Delayed three hours on the tarmac, of all things. Glad to be back at a normal desk."),
            ("A", "Rough way to end a trip. Okay, let's lock down requirements. I've got a draft backlog with priorities."),
            ("B", "Go ahead."),
            ("A", "Onboarding flow rebuild and payments integration are both P0, they gate launch. Visual refresh is P1, and dark mode specifically stays a stretch item within that. Legal and privacy review is a hard gate, and analytics instrumentation is P1."),
            ("B", "Makes sense. And localization, the thing from kickoff?"),
            ("A", "Cutting it from this release. It's a real request, but it's not worth the schedule risk right now."),
            ("B", "Okay, I'll mark it explicitly out of scope in the backlog rather than just leaving it off, so nobody assumes it got missed."),
            ("A", "Good call. Sprint cadence: two-week sprints, seven of them before code freeze, then test plan, UAT, and launch prep after that."),
            ("B", "Works for me. Legal engagement started this week, by the way, I got the intro email out."),
            ("A", "Nice, that's ahead of schedule. Analytics scoping request went out too, waiting to hear back."),
            ("B", "Sounds like we're in good shape. Next up is design review once mockups are ready."),
            ("A", "Right, talk then."),
        ],
    },
    {
        "slug": "03-design-review",
        "label": "Design Review",
        "meeting_type": "design_review",
        "intro": "This is the design review meeting for the mobile app redesign project.",
        "dialogue": [
            ("A", "Have you tried the new coffee blend they put in the break room?"),
            ("B", "I have, it's dangerously good, I've had two cups already this morning."),
            ("A", "Same. Okay, let's walk through the mockups. Onboarding flow first."),
            ("B", "These look great, much cleaner than the current flow. Fewer steps too."),
            ("A", "Agreed. Now the visual refresh, including the dark mode variant."),
            ("B", "This is really strong. Honestly, a stakeholder in the design walkthrough pushed hard for this not to be a stretch goal, they want it committed."),
            ("A", "I heard the same feedback. Let's promote dark mode from stretch to committed P1 scope, it's worth the extra sprint or two."),
            ("B", "That'll add real work, but I agree it's worth it. I'll update the backlog priority."),
            ("A", "Also, accessibility check on dark mode, contrast ratios?"),
            ("B", "Design already validated those, we're good there."),
            ("A", "Great. Last thing, payments sandbox access — did that come through?"),
            ("B", "Yes, provisioning started this week. We'll be able to start integration work Monday."),
            ("A", "Perfect, sprint one starts Monday then."),
        ],
    },
    {
        "slug": "04-sprint-status-1",
        "label": "Sprint 1 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint one status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "Did you get out for that hike this weekend?"),
            ("B", "We did, perfect weather for it, though my legs are still feeling it today."),
            ("A", "Worth it though. Alright, sprint one status. Onboarding flow?"),
            ("B", "Development started, on track, no surprises yet."),
            ("A", "Payments?"),
            ("B", "Sandbox environment is stood up. We ran our first smoke tests, and honestly it felt a little flaky. Nothing alarming yet, but worth watching."),
            ("A", "Noted, let's keep an eye on it. Dark mode?"),
            ("B", "Not started yet, it's queued right after onboarding wraps."),
            ("A", "Legal?"),
            ("B", "Review officially kicked off this week, waiting on their read."),
            ("A", "And analytics?"),
            ("B", "Events are being scoped with their team this week."),
            ("A", "Good, solid first sprint. Let's sync again in two weeks."),
        ],
    },
    {
        "slug": "05-sprint-status-2",
        "label": "Sprint 2 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint two status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "How'd the plumbing repair go? You mentioned it last time."),
            ("B", "Finally fixed, took the plumber three visits to actually find the leak."),
            ("A", "Glad that's over. Okay, sprint two. Payments sandbox, last time it felt a little flaky."),
            ("B", "It's gotten worse. The vendor's sandbox has been unstable most of this sprint, QA's partially blocked."),
            ("A", "That's a bigger deal than I expected. What's the plan if it doesn't stabilize?"),
            ("B", "If it's not stable by our next check, I'd rather delay the payments sign-off than rush it through half-tested."),
            ("A", "Agreed, quality over the deadline there. Onboarding?"),
            ("B", "On track, first internal build is ready for review."),
            ("A", "Dark mode?"),
            ("B", "An engineer starts on it this sprint, since it's committed scope now, not a stretch."),
            ("A", "Good. Legal?"),
            ("B", "Still reviewing, no answer yet."),
            ("A", "And analytics, any response to the scoping request?"),
            ("B", "Not yet, I'll chase them, it's becoming a risk."),
            ("A", "Let's regroup in two weeks."),
        ],
    },
    {
        "slug": "06-sprint-status-3",
        "label": "Sprint 3 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint three status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "Good game night this weekend? You mentioned you had people over."),
            ("B", "It was, though I lost badly at cards two rounds in a row."),
            ("A", "Ha, better luck next time. Alright, sprint three. Payments sandbox, still the same story?"),
            ("B", "Still broken, this is the third sprint running now. QA's only been able to run about half their test cases."),
            ("A", "That's frustrating. Are we still holding the line on not shipping it half-tested?"),
            ("B", "Yes, and I think it's time to escalate to the vendor's account manager directly rather than keep waiting."),
            ("A", "Agreed, let's do that this week. Onboarding?"),
            ("B", "User testing starts this sprint, early signal looks good."),
            ("A", "Dark mode?"),
            ("B", "In progress, on track."),
            ("A", "Legal, any movement?"),
            ("B", "Nudged them again, still no answer, I'll send a second nudge."),
            ("A", "And analytics, still stuck?"),
            ("B", "Yes, honestly the original owner is overloaded, we could use an extra engineer to help push it through."),
            ("A", "I'll see who I can free up. Let's sync again in two weeks."),
        ],
    },
    {
        "slug": "07-sprint-status-4",
        "label": "Sprint 4 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint four status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "Did you end up finishing that podcast series you recommended to me?"),
            ("B", "I did, the last few episodes were the best of the season honestly."),
            ("A", "I'll bump it up my list then. Okay, sprint four. Big question first, payments, after the escalation?"),
            ("B", "The vendor actually engaged this time, their engineering team is working a fix, ETA next week."),
            ("A", "That's real progress. Onboarding?"),
            ("B", "Testing's complete, completion rate jumped noticeably from where we started."),
            ("A", "Great numbers. Dark mode?"),
            ("B", "First set of screens shipped this sprint, rest in progress."),
            ("A", "Legal, did the second nudge work?"),
            ("B", "Yes, they finally responded, just some minor edits requested on the permissions copy."),
            ("A", "Good, that's nearly done then. And the extra engineer for analytics?"),
            ("B", "Got pulled in this week, instrumentation work actually started."),
            ("A", "We're three sprints from freeze, let's keep close watch on payments especially."),
            ("B", "Agreed, talk in two weeks."),
        ],
    },
    {
        "slug": "08-sprint-status-5",
        "label": "Sprint 5 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint five status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "Brutal commute this morning, the rain turned the highway into a parking lot."),
            ("B", "Same here, added almost forty minutes. Anyway, ready for status?"),
            ("A", "Let's do it. Payments, the vendor fix?"),
            ("B", "Patch shipped Tuesday, QA's re-running the full suite and it's all passing so far."),
            ("A", "Huge relief. Dark mode?"),
            ("B", "Fully shipped now, every screen has the variant."),
            ("A", "Excellent. Legal?"),
            ("B", "Approved, the copy edits went in and they signed off."),
            ("A", "Great, that thread's closed. Analytics?"),
            ("B", "Instrumentation is wired up, we're validating the data now."),
            ("A", "One new thing, given payments handles real transaction volume, we should schedule load testing before code freeze."),
            ("B", "Good call, I hadn't raised it yet, let's get it on the plan."),
            ("A", "I'll make sure it's on the list for the test plan review later. Two weeks out."),
        ],
    },
    {
        "slug": "09-sprint-status-6",
        "label": "Sprint 6 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint six status sync for the mobile app redesign project.",
        "dialogue": [
            ("A", "How's the new puppy settling in?"),
            ("B", "Chewed through a phone charger cable yesterday, so, adjusting."),
            ("A", "Classic puppy behavior. Alright, sprint six. Payments?"),
            ("B", "Fully stable, regression suite's been green for a full week straight now. I'm comfortable signing off."),
            ("A", "That's great to hear after everything it took to get there. Analytics?"),
            ("B", "Validated, the numbers check out, we can trust them."),
            ("A", "Good. What about that load testing you flagged last time?"),
            ("B", "Test plan's being drafted now, we'll run it after code freeze."),
            ("A", "Sounds right. Everything else on track for freeze next sprint?"),
            ("B", "Yes, all P0 and P1 work is either done or on schedule to finish next sprint."),
            ("A", "Great, let's sync once more before freeze, then move into test plan review."),
        ],
    },
    {
        "slug": "10-sprint-status-7",
        "label": "Sprint 7 Status",
        "meeting_type": "sprint_status",
        "intro": "This is the sprint seven status sync for the mobile app redesign project, the last sprint before code freeze.",
        "dialogue": [
            ("A", "Did that recipe you tried over the weekend turn out okay?"),
            ("B", "Surprisingly well, actually, I might make it again for the team sometime."),
            ("A", "I'd take you up on that. Okay, final sprint status before freeze. Where do we stand?"),
            ("B", "Onboarding, payments, dark mode, legal, and analytics are all complete."),
            ("A", "Feature complete, that's a great place to be. Code freeze is officially this Friday then."),
            ("B", "Agreed. The load test plan is finalized, ready to execute next week."),
            ("A", "Good, and QA's prepping the full regression pass?"),
            ("B", "Yes, that kicks off right after freeze, alongside the load test."),
            ("A", "Perfect. Next up is the formal test plan review, then UAT after that."),
            ("B", "Sounds good, talk then."),
        ],
    },
    {
        "slug": "11-test-plan-review",
        "label": "Test Plan Review",
        "meeting_type": "test_plan_review",
        "intro": "This is the test plan review meeting for the mobile app redesign project, held just after code freeze.",
        "dialogue": [
            ("A", "Good concert last night? You mentioned you had tickets."),
            ("B", "It was great, though my ears are still ringing a little this morning."),
            ("A", "Worth it though, I bet. Okay, let's go through the test plan."),
            ("B", "Sure. Functional regression across the full app, the load and performance test we scoped, a security and privacy checklist pass given the payments and permissions work, and a browser and device compatibility matrix."),
            ("A", "What's entry and exit criteria?"),
            ("B", "Entry is code freeze, which we already hit. Exit is zero open P0 or P1 bugs, plus the load test passing our response-time and concurrency thresholds."),
            ("A", "Sounds solid. When does UAT start?"),
            ("B", "We're targeting a start in two weeks, running for about one week with daily triage calls."),
            ("A", "Good, let's get testers recruited before then."),
            ("B", "I'll start on that this week."),
        ],
    },
    {
        "slug": "12-uat-kickoff",
        "label": "UAT Kickoff",
        "meeting_type": "uat_kickoff",
        "intro": "This is the UAT kickoff meeting for the mobile app redesign project.",
        "dialogue": [
            ("A", "Did the new phone you upgraded to arrive yet?"),
            ("B", "Yesterday, still transferring everything over, always such a hassle."),
            ("A", "Always is. Okay, UAT kickoff. Where do we stand on testers?"),
            ("B", "Eight external testers recruited, plus two internal stakeholders, all confirmed for next week."),
            ("A", "Great. What's the scope?"),
            ("B", "Full app flow, including payments end to end and the dark mode variant. I've written scripts covering the main paths."),
            ("A", "Good. Anything come up in the pre-brief with testers?"),
            ("B", "One of the internal stakeholders asked again about support for other languages."),
            ("A", "Right, same one from kickoff probably. Let's be clear, that was explicitly cut from this release at requirements review, it's a future request, not something we missed."),
            ("B", "I'll make sure that's communicated clearly in the response."),
            ("A", "Good. One week of testing, daily triage calls starting tomorrow."),
            ("B", "Sounds good, talk tomorrow."),
        ],
    },
    {
        "slug": "13-uat-results",
        "label": "UAT Results / Bug Triage",
        "meeting_type": "uat_results",
        "intro": "This is the UAT results and bug triage meeting for the mobile app redesign project, at the end of the UAT week.",
        "dialogue": [
            ("A", "Rough morning, the elevator's been out at the office all week."),
            ("B", "I heard, five flights is no joke. Anyway, want the UAT results?"),
            ("A", "Yes, let's go."),
            ("B", "Overall positive. Only a handful of bugs. One is a P1 in payments, a specific card type fails silently under a certain edge case. A couple of P2 and P3 cosmetic issues elsewhere."),
            ("A", "Does the P1 block launch?"),
            ("B", "I think it has to, payments is core to this release, we can't ship a silent failure there."),
            ("A", "Agreed, that gets fixed before go-live. What about the load test?"),
            ("B", "Passed our target concurrency overall, one caveat, it slows down under a specific spiky load pattern. We've already identified the fix."),
            ("A", "Good, get that scheduled too. And the localization question from UAT?"),
            ("B", "I've formally logged it as a backlog item for a future release, it's tracked now, not just a verbal note."),
            ("A", "Perfect, that closes that thread properly. Fix cycle this week, then go-live readiness review."),
            ("B", "Sounds good."),
        ],
    },
    {
        "slug": "14-go-live-readiness",
        "label": "Go-Live Readiness Review",
        "meeting_type": "go_live_readiness",
        "intro": "This is the go-live readiness review for the mobile app redesign project.",
        "dialogue": [
            ("A", "Honestly a little nervous today, first launch review always gets me."),
            ("B", "Same, though I think we're in good shape. Should we get into it?"),
            ("A", "Let's do it. The payments P1 bug from UAT?"),
            ("B", "Fixed and retested, passing cleanly now."),
            ("A", "And the load test caveat?"),
            ("B", "Also addressed, we re-ran it and it's within thresholds under the spiky pattern now."),
            ("A", "Great. Support readiness?"),
            ("B", "Help center articles are updated, support team's been briefed on the new flows."),
            ("A", "Good. Marketing has launch comms scheduled to go out on launch day, timed with the release."),
            ("B", "That's coordinated on our end too."),
            ("A", "One more thing, and I should have flagged this sooner. The payments fire drill, the vendor escalation and the extra contractor we pulled in for that week, pushed us over budget by a meaningful amount."),
            ("B", "That's good to know. Does it block launch?"),
            ("A", "No, but it needs to be reported to finance right after we launch, not swept under the rug."),
            ("B", "Agreed, let's put that on next week's agenda."),
            ("A", "Given everything else is green, I'm calling it, this is a go."),
            ("B", "Go from my side too. Launch date is confirmed."),
        ],
    },
    {
        "slug": "15-launch-retro",
        "label": "Launch Retro",
        "meeting_type": "launch_retro",
        "intro": (
            "This is the launch retro, the fifteenth and final recording in this "
            "series, held the week after the mobile app redesign officially launched."
        ),
        "dialogue": [
            ("A", "Still a little tired from the launch day pizza party, honestly."),
            ("B", "Same, but a good kind of tired. Should we get into the retro?"),
            ("A", "Let's do it. Overall, launch went smoothly, no major incidents, and early adoption numbers look positive."),
            ("B", "Agreed. What went well?"),
            ("A", "Dark mode's gotten a lot of positive feedback already, and onboarding completion is way up from where we started."),
            ("B", "And payments has been rock-solid since launch, which honestly still surprises me given how rough the middle of the project was."),
            ("A", "Same. What didn't go well?"),
            ("B", "The payments vendor instability cost us real time in the middle of the project, and led to the budget overrun you flagged last week."),
            ("A", "Right, I'm reporting that to finance this week as planned. I also think vendor stability should be a formal criterion the next time we pick a payments provider."),
            ("B", "Agreed, I'll write that up as a lesson learned."),
            ("A", "The localization request is logged for next roadmap cycle, so that's properly closed out rather than forgotten."),
            ("B", "And the post-launch analytics dashboard is live, I'll be watching it closely for the next two weeks."),
            ("A", "Good. Thanks for everything these past five months, this is the last one of these, the series ends here."),
            ("B", "Thanks, it was a good run."),
        ],
    },
]
