import hashlib
from pathlib import Path
from typing import Any

from app.config import BACKEND_DIR

try:
    import edge_tts  # type: ignore[import-untyped]
except ImportError:
    edge_tts = None


class TtsUnavailableError(RuntimeError):
    """Raised when edge-tts is not installed, network is unreachable, or no Kannada voice exists."""


MAX_TTS_TEXT_LENGTH = 500
_CACHE_DIR = (BACKEND_DIR.parent / "storage" / "tts_cache").resolve()
_memory_cache: dict[str, tuple[bytes, str]] = {}
_discovered_voice_cache: list[dict[str, str]] | None = None


def _sanitize_tts_text(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    if not cleaned:
        raise ValueError("TTS text cannot be empty.")
    return cleaned[:MAX_TTS_TEXT_LENGTH]


async def discover_kannada_voices(*, force_refresh: bool = False) -> list[dict[str, str]]:
    """Dynamically query edge-tts for confirmed Kannada (kn-IN / kn) voices."""
    global _discovered_voice_cache
    if edge_tts is None:
        raise TtsUnavailableError("edge-tts package is not installed on the backend server.")

    if _discovered_voice_cache is not None and not force_refresh:
        return _discovered_voice_cache

    try:
        all_voices = await edge_tts.list_voices()
    except Exception as exc:
        raise TtsUnavailableError(
            f"Unable to reach TTS voice directory (internet required): {exc}"
        ) from exc

    kn_voices: list[dict[str, str]] = []
    for v in all_voices:
        locale = str(v.get("Locale", "")).lower()
        if locale.startswith("kn"):
            kn_voices.append(
                {
                    "short_name": str(v.get("ShortName", "")),
                    "friendly_name": str(v.get("FriendlyName", "")),
                    "locale": str(v.get("Locale", "")),
                    "gender": str(v.get("Gender", "")),
                }
            )

    if not kn_voices:
        raise TtsUnavailableError("No Kannada (kn) voices were returned by edge-tts.")

    _discovered_voice_cache = kn_voices
    return kn_voices


async def get_kannada_tts_status() -> dict[str, Any]:
    """Return live diagnostic status of the backend edge-tts Kannada fallback."""
    if edge_tts is None:
        return {
            "provider": "edge-tts",
            "package_installed": False,
            "available": False,
            "internet_required": True,
            "kannada_voices": [],
            "selected_voice": None,
            "error": "edge-tts Python package is not installed on the backend.",
        }

    try:
        voices = await discover_kannada_voices()
        selected = next(
            (v["short_name"] for v in voices if v["locale"].lower() == "kn-in"),
            voices[0]["short_name"],
        )
        return {
            "provider": "edge-tts",
            "package_installed": True,
            "available": True,
            "internet_required": True,
            "kannada_voices": voices,
            "selected_voice": selected,
            "error": None,
        }
    except TtsUnavailableError as exc:
        return {
            "provider": "edge-tts",
            "package_installed": True,
            "available": False,
            "internet_required": True,
            "kannada_voices": [],
            "selected_voice": None,
            "error": str(exc),
        }


async def synthesize_kannada_speech(text: str) -> tuple[bytes, str, bool]:
    """Synthesize Kannada speech to MP3 bytes via edge-tts with local caching.

    Returns (mp3_bytes, voice_short_name, from_cache).
    """
    clean_text = _sanitize_tts_text(text)
    cache_key = hashlib.sha256(clean_text.encode("utf-8")).hexdigest()

    if cache_key in _memory_cache:
        audio_bytes, voice_name = _memory_cache[cache_key]
        return audio_bytes, voice_name, True

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    disk_file = _CACHE_DIR / f"{cache_key}.mp3"
    meta_file = _CACHE_DIR / f"{cache_key}.voice"
    if disk_file.is_file() and meta_file.is_file():
        audio_bytes = disk_file.read_bytes()
        voice_name = meta_file.read_text(encoding="utf-8").strip()
        if audio_bytes and voice_name:
            _memory_cache[cache_key] = (audio_bytes, voice_name)
            return audio_bytes, voice_name, True

    voices = await discover_kannada_voices()
    selected_voice = next(
        (v["short_name"] for v in voices if v["locale"].lower() == "kn-in"),
        voices[0]["short_name"],
    )

    try:
        communicate = edge_tts.Communicate(clean_text, selected_voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        audio_bytes = b"".join(chunks)
    except Exception as exc:
        raise TtsUnavailableError(f"edge-tts synthesis failed: {exc}") from exc

    if not audio_bytes:
        raise TtsUnavailableError("edge-tts returned empty audio stream.")

    _memory_cache[cache_key] = (audio_bytes, selected_voice)
    try:
        disk_file.write_bytes(audio_bytes)
        meta_file.write_text(selected_voice, encoding="utf-8")
    except OSError:
        pass

    return audio_bytes, selected_voice, False
