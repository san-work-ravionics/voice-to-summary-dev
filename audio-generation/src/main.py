import argparse
import os

from dialogues import MEETINGS
from generate_audio import generate_all

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_ROOT, "output")


def run(regenerate=False):
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if regenerate:
        for meeting in MEETINGS:
            recording_path = os.path.join(OUTPUT_DIR, meeting["slug"], "recording.wav")
            if os.path.exists(recording_path):
                os.remove(recording_path)

    template = os.path.join(OUTPUT_DIR, "{slug}", "recording.wav")
    print(f"Generating {len(MEETINGS)} recordings...")
    generate_all(output_dir_template=template)
    print(f"\nDone. All {len(MEETINGS)} recordings written under {OUTPUT_DIR}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate the 15 audio recordings for the mobile app "
        "redesign project's full lifecycle, kickoff through launch retro."
    )
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Regenerate all 15 recordings even if they already exist",
    )
    args = parser.parse_args()
    run(regenerate=args.regenerate)


if __name__ == "__main__":
    main()
