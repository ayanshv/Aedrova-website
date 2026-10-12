import io
import wave

import pytest

from aedrova_site.file_policy import inspect_file


def audio(seconds=1, channels=1, rate=16000):
    result = io.BytesIO()
    with wave.open(result, "wb") as wav:
        wav.setnchannels(channels)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(b"\0\0" * rate * seconds * channels)
    return result.getvalue()


def test_server_accepts_only_bounded_voice_pcm():
    assert inspect_file("voice.wav", audio()) == "audio/wav"
    for data in (audio(31), audio(channels=2), audio(rate=48000), audio()[:-2], audio() + b"junk"):
        with pytest.raises(ValueError):
            inspect_file("voice.wav", data)
