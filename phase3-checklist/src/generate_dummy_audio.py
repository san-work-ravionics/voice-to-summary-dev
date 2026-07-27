import os
import tempfile

import pyttsx3
from pydub import AudioSegment

PREFERRED_VOICE_NAMES = [
    "Alex", "Samantha", "Victoria", "Daniel", "Karen", "Moira", "Tessa", "Fred",
]

NARRATOR_PREFERRED_VOICE_NAMES = [
    "Daniel", "Karen", "Moira", "Tessa", "Alex", "Victoria",
]

SPEAKER_NAMES = {"A": "Sam", "B": "Priya"}

INTRO_TEXT = (
    "You are about to hear a short, two person status update meeting about "
    "the mobile app redesign project, recorded ahead of Friday's stakeholder review."
)

DIALOGUE = [
    ("A", "Hey, thanks for jumping on this call. I wanted to get a quick status update on the mobile app redesign before Friday's stakeholder review."),
    ("B", "Of course, happy to walk you through where things stand. Overall we're in decent shape, but there are a couple of areas I want to flag."),
    ("A", "Let's start with the good news. How's the new onboarding flow coming along?"),
    ("B", "The onboarding flow is basically done. We finished user testing last week with twelve participants, and the completion rate jumped from sixty percent to eighty-eight percent compared to the old flow."),
    ("A", "That's a huge improvement. Did the feedback highlight anything we should still polish?"),
    ("B", "A few people mentioned the permissions screen felt a bit abrupt. We're planning to add a short explainer before we ask for notification access, so users understand why we need it."),
    ("A", "Makes sense, small tweak, big trust impact. What about the payments integration? That was the riskiest piece."),
    ("B", "Payments is trickier. The new provider's sandbox environment has been unstable this week, so QA has only been able to run about half of the test cases."),
    ("A", "Is that going to slip the Friday deadline?"),
    ("B", "It might push checkout testing into early next week, but the core redesign work itself is still on track. I'd rather delay the payments sign-off than ship it half tested."),
    ("A", "Agreed, that's the right call. I'll let the stakeholders know payments verification needs a few extra days, but the redesign itself will be ready to demo."),
    ("B", "That would help a lot. On the design side, we also finished the dark mode variant for every screen, so we can show that off too."),
    ("A", "Nice, that wasn't even on the original roadmap for this release."),
    ("B", "The design team had some extra bandwidth after the onboarding work wrapped early, so they got ahead of schedule."),
    ("A", "Great initiative. What do you need from me before Friday?"),
    ("B", "Two things. First, could you confirm with legal whether the updated privacy language for the permissions screen is approved? Second, we could use another engineer for a day or two to help clear the payments test backlog."),
    ("A", "I'll ping legal today and try to pull someone from the platform team to help with QA."),
    ("B", "Perfect, that should get us most of the way there."),
    ("A", "Anything else blocking you right now?"),
    ("B", "Not blocking, but a heads up: the analytics events for the new flow aren't fully wired up yet, so we won't have usage data in time for the review. We'll have that ready the following week."),
    ("A", "That's fine, we can present the completion rate improvement from testing instead. Overall this sounds like a strong update."),
    ("B", "Thanks, the team's been working hard on it. I'll send you the updated deck with screenshots by tomorrow morning."),
    ("A", "Sounds good. Let's sync again Thursday afternoon to do a final check before the review."),
    ("B", "Works for me, I'll set up the invite."),
    ("A", "Great, talk to you Thursday. Thanks for the update."),
    ("B", "Thanks, talk soon."),
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
    return chosen


def _pick_voices():
    voices = pyttsx3.init().getProperty("voices")

    exclude_ids = set()
    participants = _pick_distinct(voices, PREFERRED_VOICE_NAMES, 2, exclude_ids)
    while len(participants) < 2:
        participants.append(voices[0].id)

    narrator = _pick_distinct(voices, NARRATOR_PREFERRED_VOICE_NAMES, 1, exclude_ids)
    narrator_id = narrator[0] if narrator else participants[0]

    return narrator_id, participants[0], participants[1]


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


def generate(output_path="output/recording.wav", pause_ms=500, intro_pause_ms=900):
    narrator_id, voice_a_id, voice_b_id = _pick_voices()
    same_voice = voice_a_id == voice_b_id
    base_rate = pyttsx3.init().getProperty("rate")

    with tempfile.TemporaryDirectory() as tmpdir:
        intro_path = os.path.join(tmpdir, "intro.aiff")
        _synthesize_line(INTRO_TEXT, narrator_id, base_rate, intro_path)
        recording = AudioSegment.from_file(intro_path) + AudioSegment.silent(duration=intro_pause_ms)

        silence = AudioSegment.silent(duration=pause_ms)
        for i, (speaker, line) in enumerate(DIALOGUE):
            voice_id = voice_a_id if speaker == "A" else voice_b_id
            if same_voice:
                rate = base_rate - 25 if speaker == "A" else base_rate + 25
            else:
                rate = base_rate

            clip_path = os.path.join(tmpdir, f"line_{i:03d}.aiff")
            _synthesize_line(line, voice_id, rate, clip_path)
            clip = AudioSegment.from_file(clip_path)

            recording += clip if i == 0 else silence + clip

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        recording.export(output_path, format="wav")

    minutes = len(recording) / 1000 / 60
    print(f"Generated dummy recording: {output_path} ({minutes:.1f} min, intro + {len(DIALOGUE)} lines, "
          f"{'2 distinct participant voices' if not same_voice else '1 voice with varied rate'} + narrator)")
    return output_path


if __name__ == "__main__":
    generate()
