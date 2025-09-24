"""tools/test_asr_lazy.py

Quick test harness for tools/asr_lazy.ASRManager.

This script demonstrates that importing ASRManager doesn't trigger heavy model downloads.
Run without env vars to see safe info. Optionally set VOSK_MODEL_URL to test Vosk download+transcribe.
"""

from tools.asr_lazy import ASRManager
import os


def main():
    mgr = ASRManager()
    print("ASRManager info (safe):", mgr.info())

    # Optional: if user provides TEST_AUDIO and wants to run real transcription, do it.
    test_audio = os.getenv("TEST_AUDIO")
    if test_audio:
        print("Running Whisper (may download model):")
        try:
            print(mgr.transcribe_whisper(test_audio))
        except Exception as e:
            print("Whisper failed:", e)

    test_audio_vosk = os.getenv("TEST_AUDIO_VOSK")
    if test_audio_vosk:
        print("Running Vosk (will download/extract model if VOSK_MODEL_URL is set):")
        try:
            print(mgr.transcribe_vosk(test_audio_vosk))
        except Exception as e:
            print("Vosk failed:", e)


if __name__ == "__main__":
    main()
