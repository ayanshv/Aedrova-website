"""Bounded ephemeral microphone transcription. No raw audio is written to disk."""

import base64
import binascii
import hashlib
import io
import math
import threading
import time
import wave
from uuid import UUID

import httpx
from sqlalchemy import text

from aedrova_site.store import Denied


def decode_audio(encoded):
    try:
        data = base64.b64decode(encoded, validate=True)
        if not 32044 <= len(data) <= 320044:
            raise ValueError("size")
        with wave.open(io.BytesIO(data)) as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype()) != (
                1,
                2,
                16000,
                "NONE",
            ):
                raise ValueError("format")
            n = wav.getnframes()
            pcm = wav.readframes(n)
            if not 16000 <= n <= 160000 or len(pcm) != n * 2:
                raise ValueError("duration")
            # Re-encode only PCM. Discard arbitrary RIFF metadata/trailing payloads.
            result = io.BytesIO()
            with wave.open(result, "wb") as clean:
                clean.setnchannels(1)
                clean.setsampwidth(2)
                clean.setframerate(16000)
                clean.writeframes(pcm)
        return result.getvalue(), n * 1000 // 16000
    except (ValueError, binascii.Error, wave.Error, EOFError) as error:
        raise Denied("Supply a 1–10 second mono 16 kHz PCM microphone chunk.") from error


class SpeechService:
    def __init__(self, config, store, *, transport=None):
        self.config, self.store = config, store
        self.slots = threading.BoundedSemaphore(4)
        self.client = httpx.Client(
            timeout=httpx.Timeout(10, connect=5, write=5, pool=5),
            trust_env=False,
            follow_redirects=False,
            transport=transport,
        )

    def close(self):
        self.client.close()

    def database(self, operation, values):
        sql = {
            "reserve": "select public.reserve_meeting_speech(:user, :meeting, :identifier, "
            ":revision, CAST(:roster AS uuid[]), :digest, :offset, :duration)",
            "finish": "select public.finish_meeting_speech(:user, :identifier, :body)",
        }[operation]
        try:
            with self.store.engine.begin() as connection:
                return connection.execute(text(sql), values).scalar_one()
        except Exception as error:
            raise Denied(
                "Transcription access, consent or allowance changed. "
                "Discard this chunk and refresh the meeting."
            ) from error

    def transcribe(self, user, body, *, workspace=None):
        if not self.config.speech_enabled:
            raise Denied("Audio transcription is not enabled.")
        audio, duration = decode_audio(body.audio)
        values = dict(
            user=str(UUID(user)),
            meeting=str(body.meeting),
            identifier=str(body.identifier),
            revision=body.revision,
            roster=sorted(str(u) for u in body.roster),
            digest=hashlib.sha256(audio).hexdigest(),
            offset=body.offset_ms,
            duration=duration,
        )
        if not self.slots.acquire(blocking=False):
            raise Denied("Transcription is busy. This chunk was not sent. Retry when ready.")
        access = None
        reservation = None
        try:
            state = self.database("reserve", values)
            if state == "completed":
                return {"id": values["identifier"], "replayed": True}
            if state != "pending":
                raise Denied("Speech reservation was not accepted.")
            try:
                if self.store is not None:
                    if not workspace:
                        raise Denied("Transcription requires a verified billing workspace.")
                    access = self.store.create_run(
                        user, workspace, "speech", "speech:" + values["identifier"]
                    )
                    run = self.store.run(access["token"])
                    estimate = math.ceil(duration / 1000) * math.ceil(
                        self.config.speech_rate_microusd_per_minute / 60
                    )
                    reservation, _ = self.store.reserve(
                        run, values["digest"], estimate, {"id": "whisper-1"}
                    )
                # Stream response with a hard bound; never echo provider bodies or keys.
                started = time.monotonic()
                with self.client.stream(
                    "POST",
                    "https://api.openai.com/v1/audio/transcriptions",
                    headers={
                        "Authorization": "Bearer " + self.config.speech_key,
                        "Accept-Encoding": "identity",
                    },
                    data={"model": "whisper-1", "response_format": "json"},
                    files={"file": ("microphone.wav", audio, "audio/wav")},
                ) as response:
                    response.raise_for_status()
                    chunks = bytearray()
                    for chunk in response.iter_bytes():
                        if time.monotonic() - started > 25:
                            raise TimeoutError("speech processing deadline")
                        if len(chunks) + len(chunk) > 16384:
                            raise ValueError("oversized transcript")
                        chunks.extend(chunk)
                    import json

                    result = json.loads(chunks)
                    transcript = result.get("text")
                    if not isinstance(transcript, str) or len(transcript.strip()) > 2000:
                        raise ValueError("invalid transcript")
                identifier = self.database("finish", {**values, "body": transcript.strip() or None})
                if reservation:
                    self.store.settle(reservation, estimate, b"completed")
                return {"id": str(identifier) if identifier else None, "review_required": True}
            except Exception as error:
                if reservation:
                    self.store.settle(reservation, None)
                try:
                    self.database("finish", {**values, "body": None})
                except Denied:
                    pass
                raise Denied(
                    "This speech chunk could not be saved. Check consent, "
                    "provider availability and allowance. No automatic retry."
                ) from error
        finally:
            if access:
                self.store.end_run(access["id"], user)
            self.slots.release()
