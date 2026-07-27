import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from transcription import transcribe


def main():
    audio_path = sys.argv[1] if len(sys.argv) > 1 else "output/recording.wav"
    transcript_path = "output/transcript.txt"

    text = transcribe(audio_path)

    os.makedirs(os.path.dirname(transcript_path) or ".", exist_ok=True)
    with open(transcript_path, "w") as f:
        f.write(text)

    print(f"Transcript written to {transcript_path}")
    print(text)


if __name__ == "__main__":
    main()
