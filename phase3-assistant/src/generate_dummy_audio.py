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

SPEAKER_NAMES = {"A": "Sam", "B": "Priya"}

DIALOGUE = [
    ("A", "Before we start, Assistant will be taking notes for us today and will summarize the meeting once we're done."),
    ("ASSISTANT", "Sounds good. I'll listen in, note the key points, and give you a summary at the end."),
    ("A", "Great, let's start with the good news. How's the new onboarding flow coming along?"),
    ("B", "The onboarding flow is basically done. We finished user testing last week with twelve participants, and the completion rate jumped from sixty percent to eighty-eight percent."),
    ("A", "That's a huge improvement. Assistant, can you make a note of that?"),
    ("ASSISTANT", "Noted. Onboarding testing showed completion rate improve from sixty to eighty-eight percent."),
    ("A", "What about the payments integration? That was the riskiest piece."),
    ("B", "Payments is trickier. The new provider's sandbox environment has been unstable this week, so QA has only run about half the test cases. I'd rather delay the payments sign-off than ship it half tested."),
    ("A", "Agreed. Assistant, please note that payments sign-off is delayed."),
    ("ASSISTANT", "Got it. Noted that payments sign-off will slip past Friday, but the core redesign stays on track."),
    ("B", "On the design side, we also finished the dark mode variant for every screen."),
    ("A", "Nice, that wasn't even on the roadmap for this release. Assistant, note that as a bonus win."),
    ("ASSISTANT", "Noted. Dark mode shipped ahead of schedule as a bonus."),
    ("A", "What do you need from me before Friday?"),
    ("B", "Could you confirm with legal whether the updated privacy language for the permissions screen is approved? Also, we could use another engineer for a day or two to help clear the payments test backlog."),
    ("A", "I'll ping legal today and try to pull someone from the platform team to help with QA."),
    ("B", "One more thing: the analytics events for the new flow aren't fully wired up yet, so we won't have usage data in time for the review."),
    ("A", "That's fine, we'll present the completion rate improvement instead. Let's sync again Thursday afternoon for a final check before the review."),
    ("B", "Works for me, I'll set up the invite."),
    ("A", "Assistant, based on our checklist, did we miss any topics?"),
    ("ASSISTANT", "You covered onboarding, payments, design, legal, analytics, and next steps. Budget or cost impact for this release wasn't discussed."),
    ("A", "Good catch, we'll pick that up separately. Assistant, can you summarize the meeting for us?"),
    ("ASSISTANT", "Sure. This was a status sync on the mobile app redesign ahead of Friday's stakeholder review. Onboarding is complete with an eighty-eight percent completion rate. Payments sign-off will slip a few days due to sandbox instability, but the core redesign stays on track. Dark mode shipped as a bonus. Key follow-ups: confirm legal approval on privacy language, pull in an extra engineer for payments QA, and sync again Thursday. Budget impact wasn't covered and should be picked up separately."),
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
