"""tools/asr_lazy.py

Lightweight, safe, lazy-loading helper for Whisper and Vosk.

Usage:
  from tools.asr_lazy import ASRManager
  mgr = ASRManager()
  mgr.info()  # safe: doesn't download or load heavy models
  # when ready to transcribe:
  text = mgr.transcribe_whisper('/path/to/audio.wav')
  text2 = mgr.transcribe_vosk('/path/to/audio_16k.wav')

Configuration via environment variables:
  VOSK_MODEL_URL    - optional signed/public URL to a Vosk model zip (will be downloaded and extracted on first use)
  VOSK_LOCAL_DIR    - local path where the Vosk model folder should live (default: ./models/vosk-model-small-en-us-0.15)
  WHISPER_MODEL_NAME - whisper model name (tiny, base, small, etc.). Default 'tiny'.

This module deliberately avoids importing heavy packages until methods that require them are called.
"""

from __future__ import annotations

import os
from pathlib import Path
from threading import Lock
import zipfile
import shutil


class ASRManager:
    """Lazy-loading manager for Whisper and Vosk models.

    This class won't import or download models until you call the transcription methods.
    It exposes small helper methods to check state, download Vosk archives (if a URL is provided),
    and run transcriptions.
    """

    def __init__(self):
        self.whisper_model_name = os.getenv("WHISPER_MODEL_NAME", "tiny")
        self.vosk_model_url = os.getenv("VOSK_MODEL_URL")
        self.vosk_local_dir = Path(os.getenv("VOSK_LOCAL_DIR", "./models/vosk-model-small-en-us-0.15"))

        self._whisper = None
        self._vosk = None
        self._whisper_lock = Lock()
        self._vosk_lock = Lock()

    # ----- Introspection -----
    @property
    def whisper_loaded(self) -> bool:
        return self._whisper is not None

    @property
    def vosk_loaded(self) -> bool:
        return self._vosk is not None

    def info(self) -> dict:
        return {
            "whisper_model_name": self.whisper_model_name,
            "whisper_loaded": self.whisper_loaded,
            "vosk_model_url": self.vosk_model_url,
            "vosk_local_dir": str(self.vosk_local_dir),
            "vosk_loaded": self.vosk_loaded,
        }

    # ----- Whisper -----
    def _load_whisper(self):
        with self._whisper_lock:
            if self._whisper is not None:
                return self._whisper
            try:
                import whisper
            except Exception as e:  # pragma: no cover - environment dependent
                raise RuntimeError("OpenAI Whisper package is not available: install openai-whisper and torch") from e
            # This may download the model into whisper's cache if not present
            self._whisper = whisper.load_model(self.whisper_model_name)
            return self._whisper

    def transcribe_whisper(self, audio_path: str) -> str:
        """Transcribe audio with Whisper (loads model lazily)."""
        model = self._load_whisper()
        result = model.transcribe(audio_path)
        return result.get("text", "")

    # ----- Vosk -----
    def _download_file(self, url: str, out_path: Path):
        # import here to avoid requests dependency unless needed
        try:
            import requests
        except Exception as e:  # pragma: no cover - environment dependent
            raise RuntimeError("requests is required to download Vosk model; please pip install requests") from e

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    if chunk:
                        f.write(chunk)

    def _ensure_vosk_model_on_disk(self):
        if self.vosk_local_dir.exists():
            return
        if not self.vosk_model_url:
            raise RuntimeError(
                f"Vosk model not found at {self.vosk_local_dir} and VOSK_MODEL_URL is not set."
            )

        # download zip to models dir
        archive_name = Path(self.vosk_model_url.split("?", 1)[0].split("/")[-1])
        target_zip = Path(self.vosk_local_dir.parent) / archive_name
        if not target_zip.exists():
            self._download_file(self.vosk_model_url, target_zip)

        # extract
        if zipfile.is_zipfile(target_zip):
            with zipfile.ZipFile(target_zip, "r") as z:
                z.extractall(target_zip.parent)
            # Some Vosk zips extract into a top-level folder; attempt to find it
            # If extraction created the expected folder name, we're done.
            if not self.vosk_local_dir.exists():
                # try to locate a single directory that looks like a vosk model
                for child in target_zip.parent.iterdir():
                    if child.is_dir() and child.name.startswith("vosk-model"):
                        # move/rename to desired path
                        try:
                            child.rename(self.vosk_local_dir)
                        except Exception:
                            # fallback: leave as-is and attempt to load from child
                            pass
        else:
            raise RuntimeError(f"Downloaded Vosk archive {target_zip} is not a zip file")

    def _load_vosk(self):
        with self._vosk_lock:
            if self._vosk is not None:
                return self._vosk
            try:
                from vosk import Model
            except Exception as e:  # pragma: no cover - environment dependent
                raise RuntimeError("Vosk package not available: pip install vosk") from e

            # ensure model dir exists (download+extract if VOSK_MODEL_URL provided)
            self._ensure_vosk_model_on_disk()
            self._vosk = Model(str(self.vosk_local_dir))
            return self._vosk

    def transcribe_vosk(self, audio_path: str) -> str:
        """Transcribe a 16k mono WAV with Vosk. Downloads/extracts model if needed.

        Note: Vosk expects 16k mono WAV. Convert beforehand with ffmpeg if necessary.
        """
        model = self._load_vosk()
        # local import for smaller startup cost
        import wave, json
        from vosk import KaldiRecognizer

        wf = wave.open(audio_path, "rb")
        rec = KaldiRecognizer(model, wf.getframerate())
        results = []
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            if rec.AcceptWaveform(data):
                try:
                    results.append(json.loads(rec.Result()))
                except Exception:
                    pass
        try:
            results.append(json.loads(rec.FinalResult()))
        except Exception:
            pass
        text = " ".join(r.get("text", "") for r in results)
        return text


if __name__ == "__main__":
    # Quick local demo if executed directly (non-destructive)
    mgr = ASRManager()
    print(mgr.info())
