"""Bounded content inspection. No execution, extraction, rendering or network access."""

import io
import struct
import wave
import zipfile
from pathlib import PurePosixPath

MAX_BYTES = 10 * 1024 * 1024
TEXT = {
    ".txt",
    ".md",
    ".csv",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".log",
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".css",
    ".sql",
    ".xml",
    ".rst",
    ".ini",
    ".sh",
}
OFFICE = {".docx": "word/", ".xlsx": "xl/", ".pptx": "ppt/"}


def dimensions(width, height):
    if not 1 <= width <= 12000 or not 1 <= height <= 12000 or width * height > 25000000:
        raise ValueError("Image is too large. Use up to 25 megapixels and 12,000 pixels per side.")


def inspect_file(name, data):
    if not 1 <= len(data) <= MAX_BYTES:
        raise ValueError("Choose a file between 1 byte and 10 MB.")
    if not 1 <= len(name) <= 180 or any(ord(c) < 32 or c in "/\\" for c in name):
        raise ValueError("Unsupported filename.")
    suffix = PurePosixPath(name).suffix.lower()
    invalid = (
        "File content does not match its type. "
        "Choose text, PDF, PNG, JPEG, voice WAV or Office documents."
    )
    if suffix == ".wav":
        try:
            if (
                data[:4] != b"RIFF"
                or data[8:12] != b"WAVE"
                or int.from_bytes(data[4:8], "little") + 8 != len(data)
            ):
                raise ValueError(invalid)
            with wave.open(io.BytesIO(data), "rb") as audio:
                frames = audio.getnframes()
                if (
                    audio.getnchannels(),
                    audio.getsampwidth(),
                    audio.getframerate(),
                    audio.getcomptype(),
                ) != (1, 2, 16000, "NONE") or not 16000 <= frames <= 480000:
                    raise ValueError(
                        "Voice messages must be mono 16 kHz PCM WAV, between 1 and 30 seconds."
                    )
                if len(audio.readframes(frames)) != frames * 2:
                    raise ValueError(invalid)
            return "audio/wav"
        except (wave.Error, EOFError) as error:
            raise ValueError(invalid) from error
    if suffix in TEXT:
        try:
            value = data.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            raise ValueError("Text files must use UTF-8 encoding.") from error
        if any(ord(c) < 32 and c not in "\n\r\t" for c in value):
            raise ValueError(invalid)
        return "text/plain"
    if suffix == ".png" and len(data) >= 33 and data[:8] == b"\x89PNG\r\n\x1a\n":
        if data[12:16] != b"IHDR" or data[8:12] != b"\0\0\0\r" or b"IEND" not in data[-12:]:
            raise ValueError(invalid)
        dimensions(*struct.unpack(">II", data[16:24]))
        return "image/png"
    if suffix in {".jpg", ".jpeg"} and data[:2] == b"\xff\xd8" and data[-2:] == b"\xff\xd9":
        offset = 2
        for _ in range(2048):
            if offset + 4 > len(data) or data[offset] != 255:
                break
            while offset < len(data) and data[offset] == 255:
                offset += 1
            if offset + 3 > len(data):
                break
            marker = data[offset]
            offset += 1
            length = int.from_bytes(data[offset : offset + 2], "big")
            if length < 2 or offset + length > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2} and length >= 8:
                height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
                dimensions(width, height)
                return "image/jpeg"
            offset += length
        raise ValueError(invalid)
    if suffix == ".pdf" and data.startswith(b"%PDF-") and b"%%EOF" in data[-1024:]:
        return "application/pdf"  # Download only; never execute or auto-render PDF contents.
    if suffix in OFFICE:
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                entries = archive.infolist()
                if len(entries) > 200 or sum(e.file_size for e in entries) > 50 * 1024 * 1024:
                    raise ValueError("Document exceeds safe expansion limits.")
                names = {e.filename for e in entries}
                if "[Content_Types].xml" not in names or not any(
                    n.startswith(OFFICE[suffix]) for n in names
                ):
                    raise ValueError(invalid)
                for entry in entries:
                    path = PurePosixPath(entry.filename)
                    if (
                        path.is_absolute()
                        or ".." in path.parts
                        or "\\" in entry.filename
                        or entry.flag_bits & 1
                        or "vbaproject" in entry.filename.lower()
                        or entry.file_size > max(1, entry.compress_size) * 100
                    ):
                        raise ValueError(
                            "Encrypted, macro or unusually compressed documents are unsupported."
                        )
            return "application/vnd.openxmlformats-officedocument"
        except zipfile.BadZipFile as error:
            raise ValueError(invalid) from error
    raise ValueError(invalid)
