import os
import tempfile

import pyttsx3
from pydub import AudioSegment

# Order matters: first three matches become Person A / Person B / Assistant,
# picked to be three distinct accents (US/US/GB by default on macOS) so the
# assistant is audibly distinguishable from the two meeting participants.
PREFERRED_VOICE_NAMES = [
    "Samantha", "Fred", "Daniel", "Karen", "Moira", "Tessa", "Alex", "Victoria",
]

SPEAKER_NAMES = {"A": "Jordan", "B": "Priya"}

# The same kickoff meeting phase1-baseline/phase2-checklist/phase3-context/
# phase5-office-agent transcribe from audio-generation/output/01-kickoff/ —
# Person A/B lines copied verbatim from audio-generation/src/dialogues.py's
# "01-kickoff" entry, with the assistant's note-taking/checklist/closing-
# summary call-outs interleaved, so this phase's unique technique (a third
# voice in the room) is still directly comparable to the other four.
DIALOGUE = [
    ("A", "Before we start, Assistant will be taking notes for us today and will summarize the meeting once we're done."),
    ("ASSISTANT", "Sounds good. I'll listen in, note the key points, and give you a summary at the end."),
    ("A", "Thanks. Hey, thanks for making time — did you end up signing up for that half-marathon you mentioned?"),
    ("B", "I did, registration closed yesterday. Now I actually have to train for it."),
    ("A", "Ha, good luck with that. Alright, let's get started, this is our kickoff for the mobile app redesign."),
    ("B", "Excited for this one. What's the high-level goal?"),
    ("A", "Improve onboarding conversion and give the app a visual refresh, with a hard target of launching in about five months."),
    ("B", "Okay, what's the engineering scope look like?"),
    ("A", "Four workstreams: rebuilding the onboarding flow, integrating a new payments provider, the visual refresh with dark mode as a stretch goal, and we'll need legal and privacy review plus analytics instrumentation running alongside all of it."),
    ("A", "Assistant, can you note those four workstreams?"),
    ("ASSISTANT", "Noted. Four workstreams: onboarding flow rebuild, payments integration, visual refresh with dark mode as a stretch goal, and legal/analytics support."),
    ("B", "Payments is the one that worries me. New vendor means we don't know their sandbox is solid until we're in it. I want access on day one."),
    ("A", "Agreed, I'll push to get that provisioned this week. I'll also get legal engaged early so it's not a bottleneck later, and loop analytics in to start scoping events."),
    ("A", "Assistant, note that I'm owning payments sandbox access, legal engagement, and analytics scoping."),
    ("ASSISTANT", "Got it. Noted three action items owned by Person A: provision payments sandbox access, engage legal early, and loop in analytics to scope events."),
    ("B", "Sounds good. One more thing — a stakeholder asked me if this includes other languages, is localization in scope?"),
    ("A", "Not decided yet. Let's bring that to requirements review next week and settle it there rather than assume."),
    ("B", "Fair enough."),
    ("A", "Great, let's reconvene next week for requirements review, then we'll settle into two-week sprint syncs after that."),
    ("B", "Sounds good, talk then."),
    ("A", "Assistant, based on our checklist, did we miss any topics?"),
    ("ASSISTANT", "You covered onboarding, payments, design, legal, analytics, and next steps. Budget or cost impact for this release wasn't discussed."),
    ("A", "Good catch, we'll pick that up separately. Assistant, can you summarize the meeting for us?"),
    ("ASSISTANT", "Sure. This was the kickoff for the mobile app redesign project. The goal is improving onboarding conversion and delivering a visual refresh, targeting launch in about five months. Four workstreams were scoped: onboarding flow rebuild, payments integration with a new vendor, visual refresh with dark mode as a stretch goal, and legal and analytics support running alongside. Person A will provision payments sandbox access, engage legal early, and loop in analytics to scope events. Localization is still undecided and will be settled at requirements review next week, which is also when the team moves to two-week sprint syncs. Budget impact wasn't discussed and should be picked up separately."),
    ("A", "Perfect, thanks Assistant."),
    ("B", "Thanks everyone, talk soon."),
]


def _pick_distinct(voices, preferred_names, count, exclude_ids):
    chosen = []
    for name in preferred_names:
        for voice in voices:
            if name.lower() in voice.name.lower() and voice.id not in exclude_ids:
                chosen.append(voice.id)
                exclude_ids.add(voice.id)
                break
        if len(chosen) == count:
            return chosen
    for voice in voices:
        if len(chosen) == count:
            break
        if voice.id not in exclude_ids:
            chosen.append(voice.id)
            exclude_ids.add(voice.id)
    while len(chosen) < count:
        chosen.append(chosen[-1] if chosen else voices[0].id)
    return chosen


def _pick_voices():
    voices = pyttsx3.init().getProperty("voices")
    voice_a_id, voice_b_id, voice_assistant_id = _pick_distinct(voices, PREFERRED_VOICE_NAMES, 3, set())
    return voice_a_id, voice_b_id, voice_assistant_id


def _synthesize_line(text, voice_id, rate, clip_path):
    # A fresh engine per call works around a macOS pyttsx3 bug where
    # repeated save_to_file/runAndWait calls on one engine instance
    # only reliably render the first call in the loop.
    engine = pyttsx3.init()
    engine.setProperty("voice", voice_id)
    engine.setProperty("rate", rate)
    engine.save_to_file(text, clip_path)
    engine.runAndWait()
    engine.stop()


def generate(output_path="output/recording.wav", pause_ms=500):
    voice_a_id, voice_b_id, voice_assistant_id = _pick_voices()
    voice_map = {"A": voice_a_id, "B": voice_b_id, "ASSISTANT": voice_assistant_id}
    base_rate = pyttsx3.init().getProperty("rate")

    with tempfile.TemporaryDirectory() as tmpdir:
        silence = AudioSegment.silent(duration=pause_ms)
        recording = None
        for i, (speaker, line) in enumerate(DIALOGUE):
            clip_path = os.path.join(tmpdir, f"line_{i:03d}.aiff")
            _synthesize_line(line, voice_map[speaker], base_rate, clip_path)
            clip = AudioSegment.from_file(clip_path)
            recording = clip if recording is None else recording + silence + clip

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        recording.export(output_path, format="wav")

    minutes = len(recording) / 1000 / 60
    print(f"Generated dummy recording: {output_path} ({minutes:.1f} min, {len(DIALOGUE)} lines, "
          f"3 distinct voices: Person A / Person B / Assistant)")
    return output_path


if __name__ == "__main__":
    generate()
