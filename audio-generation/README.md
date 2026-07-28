# audio-generation — 15 recordings, project initiation to launch

Part of the [voice-to-summary](../README.md) project. This folder is deliberately **not** one of the `phaseN-*` scenarios — those are the demo pipelines that consume recordings and produce transcripts/summaries. This folder only produces the raw audio input: 15 scripted, synthesized meeting recordings covering the full lifecycle of the same fictional Mobile App Redesign project used elsewhere in this repo, from kickoff through launch retro (~5 months), instead of a single snapshot or a short run of same-shaped weekly syncs.

Every phase in this repo transcribes recordings from here: Phases 1-3 and 5 all transcribe `output/01-kickoff/` (the shared kickoff meeting, for direct comparability across techniques); Phase 4 re-synthesizes the kickoff dialogue with a third assistant voice added; Phase 6 transcribes and summarizes all 15 meetings as one continuous story — see [`../phase6-history/README.md`](../phase6-history/README.md).

## The 15 meetings

| # | Meeting | Type |
|---|---|---|
| 1 | Project Kickoff | initiation |
| 2 | Requirements Review | planning |
| 3 | Design Review | design |
| 4–10 | Sprint Status ×7 | build |
| 11 | Test Plan Review | QA |
| 12 | UAT Kickoff | UAT |
| 13 | UAT Results / Bug Triage | UAT |
| 14 | Go-Live Readiness Review | deployment |
| 15 | Launch Retro | post-launch |

Each is a distinct meeting *type* with its own shape, not the same status-sync format repeated. Several threads run continuously across all 15 so later meetings only make full sense with the earlier ones — a new payments vendor's sandbox goes from "a little flaky" (04) to blocking QA (05-06), gets escalated (06), fixed (07-08), and signed off (09), then resurfaces as the year's one real launch-blocking bug in UAT (13) before getting fixed and approved for go-live (14). Dark mode is promoted from stretch goal to committed scope at design review (03). A localization request is explicitly cut from scope at requirements review (02) rather than silently dropped, resurfaces as a UAT question (12), and is formally logged as a future backlog item (13) — closed out in the retro (15). Budget/cost impact is never discussed until go-live readiness (14), where a cost overrun from the payments fire-drill is flagged for the first time. See `src/dialogues.py`'s module docstring for the full thread-by-thread breakdown.

Each meeting opens with a few lines of throwaway small talk (a marathon, a delayed flight, a new puppy, ...), distinct per meeting and unrelated to the project.

## Generate

```bash
python audio-generation/src/main.py
```

Writes `output/<slug>/recording.wav` for each of the 15 meetings (e.g. `output/01-kickoff/recording.wav`). Uses local `pyttsx3` (macOS system voices) + `pydub` to synthesize and stitch each meeting's intro + dialogue lines into one `.wav`, the same approach `phase4-assistant/src/generate_dummy_audio.py` uses for its own (3-voice) recording. Two consistent voices are picked once and reused across all 15 meetings so the same two speakers (Jordan and Priya) sound the same throughout. Pass `--regenerate` to re-synthesize everything even if recordings already exist.

## Scope

This folder only generates audio. Transcription and summarization are out of scope here by design — that's each consuming phase's own job. `phase6-history/` is the phase that reads all 15 of these `.wav` files as input and adds its own transcript/summary pipeline (baseline vs. context+history) alongside them.
