
import threading
from pathlib import Path

import sherpa_onnx
import soundfile as sf

from app.config import BASE_DIR


MODEL_DIR = (
    Path(BASE_DIR)
    / "models"
    / "sherpa-onnx-zipformer-en-2023-06-26"
)

_recognizer = None
_init_lock = threading.Lock()
_decode_lock = threading.Lock()


def get_recognizer():
    """Load the Sherpa model once and reuse it."""

    global _recognizer

    if _recognizer is not None:
        return _recognizer

    with _init_lock:
        if _recognizer is not None:
            return _recognizer

        model_files = {
            "encoder": MODEL_DIR / "encoder-epoch-99-avg-1.int8.onnx",
            "decoder": MODEL_DIR / "decoder-epoch-99-avg-1.onnx",
            "joiner": MODEL_DIR / "joiner-epoch-99-avg-1.int8.onnx",
            "tokens": MODEL_DIR / "tokens.txt",
        }

        for name, path in model_files.items():
            if not path.is_file():
                raise FileNotFoundError(
                    f"Missing {name} model file: {path}"
                )

        _recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
            encoder=str(model_files["encoder"]),
            decoder=str(model_files["decoder"]),
            joiner=str(model_files["joiner"]),
            tokens=str(model_files["tokens"]),
            num_threads=2,
            sample_rate=16000,
            feature_dim=80,
            decoding_method="greedy_search",
            provider="cpu",
        )

    return _recognizer


def transcribe_audio(audio_path: str) -> str:
    """Transcribe a mono 16 kHz WAV recording."""

    recognizer = get_recognizer()

    audio, sample_rate = sf.read(
        audio_path,
        dtype="float32",
        always_2d=True,
    )

    audio = audio.mean(axis=1)

    if sample_rate != 16000:
        raise ValueError(
            f"Expected 16000 Hz audio, received {sample_rate} Hz."
        )

    if len(audio) == 0:
        return ""

    with _decode_lock:
        stream = recognizer.create_stream()
        stream.accept_waveform(sample_rate, audio)
        recognizer.decode_stream(stream)

        return stream.result.text.strip()
