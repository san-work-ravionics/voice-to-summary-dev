# phase6-history — 15 meetings, baseline vs. context-aware summarization over time (Phase 6)

Part of the [voice-to-summary](../README.md) project. phase3-context already showed that giving the summarizer *static* project background produces a sharper single-meeting summary. This asks a harder question: across a **series** of meetings, does giving the summarizer a **running history of what happened in prior meetings** produce a better summary than treating each meeting in isolation?

## The story

All 15 meetings from [`audio-generation/`](../audio-generation/README.md): the Mobile App Redesign project's full lifecycle, kickoff through launch retro, spanning roughly five months. Unlike a repeated weekly-status format, each meeting is a distinct type — kickoff, requirements review, design review, seven sprint status syncs, test plan review, UAT kickoff, UAT results/triage, go-live readiness, launch retro — and several threads run continuously across meetings so later ones only make full sense with the earlier ones (see `audio-generation/src/dialogues.py`'s module docstring for the full thread-by-thread breakdown): a new payments vendor's sandbox goes from "a little flaky" to blocking QA, gets escalated, fixed, and signed off, then resurfaces as the year's one real launch-blocking bug in UAT before being fixed and approved for go-live; dark mode is promoted from stretch goal to committed scope at design review; a localization request is explicitly cut from scope at requirements review rather than silently dropped, resurfaces as a UAT question, and is formally logged as a future backlog item.

Budget/cost impact is never discussed until go-live readiness (meeting 14), where a cost overrun from the payments fire-drill is flagged for the first time — echoing the same deliberate checklist gap from [phase2-checklist](../phase2-checklist/README.md)/[phase4-assistant](../phase4-assistant/README.md).

Each meeting also opens with a few lines of clearly non-project small talk — distinct per meeting (a half-marathon, a delayed flight, a new coffee blend, a hike, a plumbing repair, game night, a podcast, a bad commute, a new puppy, a recipe, a concert, a new phone, a broken elevator, a launch-day pizza party), worded not to collide with any real project vocabulary elsewhere in these scripts.

## Two summarizers per meeting

- **`summarize_baseline`** — the current transcript only, no memory of prior meetings. This is what every meeting would get if summarized in total isolation.
- **`summarize_with_context`** — the project's static background (like phase3-context) **plus a running history** built from the Decisions + Actions of every previous meeting's own context-aware summary. Meeting 10's context literally depends on what meetings 1-9 actually produced, not a hand-written script — the same way a person catching up from real meeting notes would.

The system prompt is explicit that history is for *interpreting* the current transcript (recognizing a callback as a continuation of a known issue), never a source of facts to state as having happened in the current meeting.

## Run

```bash
python audio-generation/src/main.py     # generates the 15 input recordings, if not done already
python phase6-history/src/main.py
```

Writes `output/<slug>/{transcript.txt, summary_baseline.txt, summary_with_context.txt}` for each of the 15 meetings (e.g. `01-kickoff/`, `15-launch-retro/`) — recordings themselves live in `audio-generation/output/<slug>/`, not copied here. Pass `--regenerate` to force re-transcription of every meeting (it can't regenerate the recordings, which belong to `audio-generation/`).

```bash
python eval/story_judge.py     # holistic faithfulness/completeness/conciseness/continuity scores
python eval/story_probes.py    # noise-leakage check + the deterministic/probe checks below
```

## Where to look for the difference

The holistic 1-5 judge scores give a modest edge to context-aware (faithfulness 4.0/5 vs. baseline's 3.9/5, completeness 3.5/5 vs. 3.3/5 — continuity is identical at 4.6/5 for both and doesn't distinguish them). The real story is in the deterministic checks, found by manually reading the actual generated text after `eval/story_probes.py` flagged them:

- **Small talk never leaks — but only for context-aware.** Baseline includes the opening small talk as a Key Point in 3 of the 15 meetings (marathon training in 01-kickoff, the coffee blend in 03-design-review, the plumbing repair in 05-sprint-status-2). Context-aware leaks in 0 of 15. A clean, consistent win for context.
- **Context-aware correctly conveys resolution where baseline hedges.** At 09-sprint-status-6, the transcript says the payments vendor issue is "fully stable... comfortable signing off." A targeted probe found baseline's summary technically says "fully stable" but doesn't make clear whether that's a *change* from before or how things always were; context-aware (which knows the sandbox was previously flagged as flaky, worse, and escalated) clearly conveys the resolution.
- **Context-aware carries stale actions forward as pending — a real cost.** At 04-sprint-status-1, the context-aware summary lists "promote dark mode to committed scope" and "confirm payments sandbox access is provisioned" as pending actions — but both were already decided/done in the *prior* meeting (03-design-review), and 04's own transcript doesn't restate them (dark mode is "not started yet", payments sandbox is already "stood up"). At 12-uat-kickoff, context-aware lists "start recruiting testers for UAT" as pending — but this meeting's own transcript says recruiting is already done ("eight external testers recruited... all confirmed"). Baseline, having no history to leak, never shows this failure mode in this run.

A deterministic "dark-mode vs. legal/privacy conflation" check (ported from an earlier 5-meeting version of this story, where it caught a real defect) flags 2 of 15 meetings here too — but manual review shows these are compact status bullets that legitimately mention every workstream together (several genuinely converge or complete around the same sprints in this richer narrative), not the semantic conflation the check was built to catch. Reported here as a negative result, not a hidden gap: this particular check doesn't generalize cleanly to this narrative's summarization style.

None of the three real findings above showed up in the holistic continuity score. See the Story page in `webapp/` for the full evidence, side by side, meeting by meeting.
