import os
import tempfile

import pyttsx3
from pydub import AudioSegment

from dialogues import MEETINGS

PREFERRED_VOICE_NAMES = [
    "Alex", "Samantha", "Victoria", "Daniel", "Karen", "Moira", "Tessa", "Fred",
]

NARRATOR_PREFERRED_VOICE_NAMES = [
    "Daniel", "Karen", "Moira", "Tessa", "Alex", "Victoria",
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
    # Picked once and reused across all 5 meetings so the same two people
    # sound the same from week to week, like a real recurring meeting.
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
    # repeated save_to_file/runAndWait calls on one engine instance only
    # reliably render the first call in the loop.
    engine = pyttsx3.init()
    engine.setProperty("voice", voice_id)
    engine.setProperty("rate", rate)
    engine.save_to_file(text, clip_path)
    engine.runAndWait()
    engine.stop()


def generate_meeting(meeting, output_path, narrator_id, voice_a_id, voice_b_id,
                      pause_ms=500, intro_pause_ms=900):
    same_voice = voice_a_id == voice_b_id
    base_rate = pyttsx3.init().getProperty("rate")

    with tempfile.TemporaryDirectory() as tmpdir:
        intro_path = os.path.join(tmpdir, "intro.aiff")
        _synthesize_line(meeting["intro"], narrator_id, base_rate, intro_path)
        recording = AudioSegment.from_file(intro_path) + AudioSegment.silent(duration=intro_pause_ms)

        silence = AudioSegment.silent(duration=pause_ms)
        for i, (speaker, line) in enumerate(meeting["dialogue"]):
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
    print(f"Generated {meeting['label']}: {output_path} ({minutes:.1f} min, "
          f"intro + {len(meeting['dialogue'])} lines)")
    return output_path


def generate_all(output_dir_template="output/meeting-{week}/recording.wav"):
    narrator_id, voice_a_id, voice_b_id = _pick_voices()
    paths = []
    for meeting in MEETINGS:
        output_path = output_dir_template.format(week=meeting["week"])
        if os.path.exists(output_path):
            print(f"Using existing recording for {meeting['label']} at {output_path}")
        else:
            generate_meeting(meeting, output_path, narrator_id, voice_a_id, voice_b_id)
        paths.append(output_path)
    return paths


if __name__ == "__main__":
    generate_all()
