import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

from audio_to_text import WhisperAudioToText


def ingest_audio(file_paths: list, model_name="small", model_dir="./models/whisper") -> dict:
    try:
        converter = WhisperAudioToText(
            model_name=model_name,
            model_dir=model_dir,
        )
    except Exception as e:
        print(f"  [audio] Whisper failed to load: {e}")
        return {}

    transcripts = {}

    for audio_path in file_paths:
        try:
            result = converter.convert_to_text(audio_path)
            text = result.get("text", "").strip()

            if not text:
                print(f"  [audio] SKIP {audio_path}: empty transcript")
                continue

            abs_path = str(os.path.abspath(audio_path))
            transcripts[abs_path] = text
            print(f"  [audio] {os.path.basename(audio_path)}: {len(text)} chars")

        except Exception as e:
            print(f"  [audio] SKIP {audio_path}: {e}")

    return transcripts