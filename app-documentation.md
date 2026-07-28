# Voice to Summary — One-Pager

## What it does

Voice to Summary turns a recorded meeting into a clear, structured written summary — automatically, and entirely on the local machine. No audio or transcript ever leaves the device, no third-party AI service is called, and no per-use API costs are incurred.

Given a meeting recording, the system:
1. **Transcribes** the conversation into text.
2. **Summarizes** it into a short, structured brief — Topic, Key Points, Decisions, and Actions.
3. **Checks coverage** against a checklist of topics the meeting was expected to address, flagging anything that was missed.
4. Optionally includes a live **AI meeting assistant** in the conversation itself, taking notes as the meeting happens and giving a closing recap before the written summary is produced.
5. Across a **series** of meetings, can carry a running history forward so later summaries correctly interpret callbacks to earlier weeks (e.g. "the issue we flagged last week") instead of treating each meeting as an isolated snapshot.

## Why it matters

- **Privacy by design.** Everything — recording, transcription, and summarization — runs locally. Nothing is uploaded to a cloud AI provider. This matters for meetings involving sensitive business, legal, or customer information.
- **No recurring cost.** There's no per-minute transcription fee or per-token AI API bill — the models run on local hardware.
- **Consistently anonymized output.** Summaries never surface personal names — participants are referred to as "Person A" / "Person B," which makes summaries safe to share more broadly (e.g. with stakeholders who don't need to know who said what).
- **Accountability built in.** Every summary separates out concrete action items, each attributed to the person who committed to it — nothing gets lost as a vague, unowned bullet point.
- **Nothing falls through the cracks.** A checklist-coverage check compares the meeting against the topics it was supposed to cover, so a manager or PM can see at a glance what was discussed and what still needs to be raised.
- **Grounded, not generic.** Feeding the summarizer background context about the project (goals, workstreams, attendees) produces sharper, more specific summaries than a bare transcript alone would — closer to what someone who attended the meeting would write.

## How it was built and proven out

The project was developed as four progressively richer capability stages against one shared input recording, each one demonstrating a specific improvement in isolation, plus a fifth stage that tests the same "context helps" idea across a realistic 15-meeting project lifecycle instead of one meeting:

| Phase | Scenario | Capability added | Business value |
|---|---|---|---|
| 1 | `phase1-baseline` | Baseline: recording → transcript → structured summary | Establishes the core automation |
| 2 | `phase2-checklist` | Checklist-based coverage check | Confidence that nothing important was missed |
| 3 | `phase3-context` | Meeting context injected into the summarizer | More accurate, specific summaries |
| 4 | `phase4-assistant` | An AI assistant present in the meeting itself | A live note-taker that recaps, checks coverage, and closes the meeting with a spoken summary |
| 6 | `phase6-history` | A 15-meeting story (kickoff through launch retro) with a running history carried forward | Tests whether context helps across time, not just within one meeting — with a real, evidenced answer: mostly yes, with a real cost (see below) |

Phase 5 (an agentic Office/on-device assistant) and Phase 7 (a voice query interface over everything above) round out the full build — see [ROADMAP.md](ROADMAP.md) for how all seven phases fit together and what each one measures.

Each stage was tested end-to-end and its output verified for accuracy before moving to the next — including a deliberate check that the checklist correctly reports both what *was* and *wasn't* discussed, not just a generic "all good."

## How quality is measured

An evaluation suite (`eval/`) scores every stage on:

- **Speech-recognition accuracy** — Word Error Rate against the exact original script, plus a noise-robustness test (synthetic background noise + a simulated poor microphone) to see how accuracy degrades under harder conditions.
- **Summary faithfulness** — does the summary only state what was actually said, with no invented facts.
- **Structure & format compliance** — does the output reliably follow the required Markdown sections.
- **Checklist coverage accuracy** — precision/recall of "was this topic actually covered" against a hand-verified ground truth.
- **Information extraction efficiency** — how many of the real commitments made in a meeting actually turn into an Actions bullet.

Two honest, evidenced findings came out of building this measurement layer, worth knowing before trusting any single number from it:

1. **A small local model is an unreliable judge of its own nuanced output.** Wherever this project used the same small local LLM to grade something subjective (faithfulness scores, checklist coverage by LLM, cross-meeting continuity, yes/no fact probes), that judge was caught giving a wrong answer on manual spot-checking — including on cases it was specifically built to catch. Deterministic checks (keyword matching, word-overlap, Word Error Rate) were used wherever possible instead, and are the more trustworthy numbers in every report this project produces.
2. **Giving the summarizer more context is not an unconditional improvement.** Across a 15-meeting project story, a summarizer with a running history scored a bit higher on faithfulness/completeness and never leaked small talk into the summary (an isolated summarizer did, 3 times) — but in 2 of the 15 meetings, that same running history caused it to present an already-finished task as if still pending. Context measurably helps in most respects and measurably hurts in a specific, real way; the honest answer is "mostly yes, with a real cost," not "context is always better." See [`phase6-history/README.md`](phase6-history/README.md) for the specific evidence.

## Use cases

- Internal status syncs and stand-ups that need a written record without someone manually taking notes.
- Pre-review or pre-stakeholder-meeting checkpoints, where a checklist ensures all required topics were actually covered.
- Any setting where meeting content is sensitive enough that sending audio to a third-party cloud transcription/AI service isn't acceptable.

---

## Technical stack

- **Language:** Python 3
- **Speech-to-text:** [OpenAI Whisper](https://github.com/openai/whisper) (local, `base` model)
- **Summarization:** local instruction-following LLM via Hugging Face `transformers` (`Qwen/Qwen2.5-1.5B-Instruct`), run on-device (Apple Silicon MPS acceleration where available; CPU otherwise, including in a container)
- **Text-to-speech (for demo/sample recordings):** `pyttsx3`, using native OS voices — macOS's built-in voices normally, `espeak-ng` when run in a Linux container; the two sound different enough that Whisper's transcription accuracy on a *regenerated* demo recording varies with which backend produced it (real audio dropped in for transcription isn't affected — it never goes through TTS)
- **Audio processing:** `pydub` (backed by `ffmpeg`)
- **Checklist coverage check:** deterministic keyword matching against the transcript, with negation-awareness — chosen over an additional LLM call after testing showed the small local model was unreliable at that specific judgment
- **Evaluation suite (`eval/`):** Word Error Rate + noise-robustness testing (no new dependency — plain word-level edit distance, plus `pydub`-generated noise), LLM-judged faithfulness/completeness/conciseness, and deterministic schema/checklist/extraction-efficiency checks — same "prefer deterministic over LLM judgment" principle as the checklist above, applied wherever it held up under testing
- **Web UI (`webapp/`):** framework-free HTML/CSS/JS, served by a stdlib-only Python `http.server` subclass — no new runtime dependency
- **Dependencies:** `torch`, `accelerate`, `transformers`, `openai-whisper`, `pydub`, `pyttsx3` — versions pinned in `requirements.txt`
- **Infrastructure:** runs entirely offline/on-device after initial one-time model downloads (~3GB total); no external API keys or network calls required at runtime
- **Containerized deployment:** `Dockerfile` + `docker-compose.yml` at the project root — `docker compose up --build` runs the same webapp and pipelines in a container (CPU-only, since Docker Desktop doesn't pass GPU/MPS through to Linux containers). Per-scenario output, custom audio, evaluation history, and logs are bind-mounted from the project directory, so the container and a local `python <scenario>/src/main.py` run share one history instead of two disconnected copies; only the downloaded models sit in a separate named Docker volume, since that's pure binary cache. A `/healthz` endpoint supports container health checks.
