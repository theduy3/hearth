"""PCM16 mono WAV helpers. No third-party audio libraries."""

from __future__ import annotations

import io
import struct
import wave

PCM_RATE = 16000
PCM_WIDTH = 2
PCM_CHANNELS = 1


def wav_header(data_bytes: int, rate: int = PCM_RATE) -> bytes:
    byte_rate = rate * PCM_CHANNELS * PCM_WIDTH
    block_align = PCM_CHANNELS * PCM_WIDTH
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_bytes,
        b"WAVE",
        b"fmt ",
        16,
        1,
        PCM_CHANNELS,
        rate,
        byte_rate,
        block_align,
        16,
        b"data",
        data_bytes,
    )


def wrap_pcm16(pcm: bytes, rate: int = PCM_RATE) -> bytes:
    return wav_header(len(pcm), rate) + pcm


def parse_wav(blob: bytes) -> tuple[bytes, int]:
    """Read complete PCM16 mono WAV using the standard library's chunk parser."""
    if len(blob) < 44 or blob[:4] != b"RIFF" or blob[8:12] != b"WAVE":
        raise ValueError("not a RIFF/WAVE file")
    if struct.unpack_from("<I", blob, 4)[0] + 8 != len(blob):
        raise ValueError("WAVE length does not match its header")
    try:
        with wave.open(io.BytesIO(blob), "rb") as reader:
            if reader.getnchannels() != 1 or reader.getsampwidth() != 2 or reader.getcomptype() != "NONE":
                raise ValueError("need uncompressed PCM16 mono WAV")
            rate = reader.getframerate()
            frames = reader.getnframes()
            pcm = reader.readframes(frames + 1)
            if not frames or len(pcm) != frames * 2:
                raise ValueError("truncated or misaligned PCM16 data")
            return pcm, rate
    except (wave.Error, EOFError, struct.error) as error:
        raise ValueError("invalid PCM16 mono WAV") from None


def clean_asr_text(text: str) -> str:
    """Qwen3-ASR wraps transcripts as `language En<asr_text>hello`."""
    marker = "<asr_text>"
    if marker in text:
        text = text.split(marker, 1)[1]
    text = text.replace("</asr_text>", "")
    text = text.strip()
    lowered = text.lower()
    if lowered in ("", "none", "null"):
        return ""
    return text
