
import io
import threading
import wave
from pathlib import Path

from piper import PiperVoice, SynthesisConfig


MODEL_PATH = (
    Path(__file__).resolve().parents[2]
    / "models"
    / "piper"
    / "en_US-lessac-medium.onnx"
)

_voice = None
_init_lock = threading.Lock()
_synthesis_lock = threading.Lock()


def get_voice():
    """Load the Piper voice once and reuse it."""
    global _voice

    if _voice is not None:
        return _voice

    with _init_lock:
        if _voice is None:
            if not MODEL_PATH.is_file():
                raise FileNotFoundError(
                    f"Piper voice model not found: {MODEL_PATH}"
                )

            _voice = PiperVoice.load(str(MODEL_PATH))

    return _voice


def synthesize_audio(text: str) -> bytes:
    """Convert text into WAV audio bytes."""

    text = text.strip()

    if not text:
        raise ValueError("Text cannot be empty.")

    if len(text) > 1000:
        raise ValueError("Text is too long.")

    voice = get_voice()
    output = io.BytesIO()

    config = SynthesisConfig(
        length_scale=0.95,
        volume=1.0,
    )

    with _synthesis_lock:
        with wave.open(output, "wb") as wav_file:
            voice.synthesize_wav(
                text,
                wav_file,
                syn_config=config,
            )

    return output.getvalue()
