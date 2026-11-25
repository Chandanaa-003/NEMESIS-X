from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
import logging
import os
from pathlib import Path
import re
import subprocess
from threading import RLock
from typing import Callable, Literal
import uuid


logger = logging.getLogger(__name__)
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_DIMENSIONS_RE = re.compile(r"\b(\d{2,5})x(\d{2,5})\b")
_FRAME_RATE_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*fps\b")
_PIXEL_FORMAT_RE = re.compile(r"\b(yuv[a-zA-Z0-9_]+|nv12|p010le)\b")


class PlaybackPreparationError(Exception):
    """Raised when a source cannot be inspected or prepared for browser playback."""


class FfmpegUnavailableError(PlaybackPreparationError):
    """Raised when the bundled FFmpeg executable is missing."""


@dataclass(frozen=True)
class VideoMetadata:
    container: str
    video_codec: str
    pixel_format: str
    width: int
    height: int
    frame_rate: float | None
    duration_seconds: float | None
    audio_codec: str | None


@dataclass(frozen=True)
class PlaybackJobState:
    status: Literal["not_started", "converting", "ready", "failed"]
    progress: int
    message: str
    path: Path | None = None


def _ffmpeg_executable() -> str:
    try:
        import imageio_ffmpeg
    except ImportError as exc:
        raise FfmpegUnavailableError(
            "FFmpeg is unavailable; install the backend playback dependencies."
        ) from exc
    try:
        executable = imageio_ffmpeg.get_ffmpeg_exe()
    except (OSError, RuntimeError) as exc:
        raise FfmpegUnavailableError("The bundled FFmpeg executable could not be located.") from exc
    if not Path(executable).is_file():
        raise FfmpegUnavailableError("The FFmpeg executable is missing.")
    return executable


def _duration_seconds(output: str) -> float | None:
    match = _DURATION_RE.search(output)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def inspect_video(path: Path) -> VideoMetadata:
    """Inspect container and stream codecs from FFmpeg's input diagnostics."""
    executable = _ffmpeg_executable()
    try:
        result = subprocess.run(
            [executable, "-hide_banner", "-i", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise PlaybackPreparationError("FFmpeg could not inspect the uploaded video.") from exc

    output = f"{result.stdout}\n{result.stderr}"
    input_match = re.search(r"Input #0,\s*([^,\s]+)", output)
    video_line = next((line for line in output.splitlines() if "Video:" in line), None)
    if not input_match or video_line is None:
        raise PlaybackPreparationError(
            "FFmpeg could not find a supported video stream in this input."
        )

    codec_match = re.search(r"\bVideo:\s*([a-zA-Z0-9_]+)", video_line)
    pixel_format_match = _PIXEL_FORMAT_RE.search(video_line)
    dimensions_match = _DIMENSIONS_RE.search(video_line)
    if not codec_match or not pixel_format_match or not dimensions_match:
        raise PlaybackPreparationError(
            "FFmpeg could not identify the input video codec, pixel format, or dimensions."
        )

    audio_line = next((line for line in output.splitlines() if "Audio:" in line), None)
    audio_match = re.search(r"\bAudio:\s*([a-zA-Z0-9_]+)", audio_line or "")
    frame_rate_match = _FRAME_RATE_RE.search(video_line)
    container = input_match.group(1).lower()
    if path.suffix.lower() == ".mp4" and container == "mov":
        container = "mp4"

    return VideoMetadata(
        container=container,
        video_codec=codec_match.group(1).lower(),
        pixel_format=pixel_format_match.group(1).lower(),
        width=int(dimensions_match.group(1)),
        height=int(dimensions_match.group(2)),
        frame_rate=float(frame_rate_match.group(1)) if frame_rate_match else None,
        duration_seconds=_duration_seconds(output),
        audio_codec=audio_match.group(1).lower() if audio_match else None,
    )


def has_faststart_metadata(path: Path) -> bool:
    """Return whether the MP4 moov atom precedes media data."""
    size = path.stat().st_size
    position = 0
    moov_position: int | None = None
    mdat_position: int | None = None
    with path.open("rb") as source:
        while position + 8 <= size:
            source.seek(position)
            header = source.read(8)
            atom_size = int.from_bytes(header[:4], "big")
            atom_name = header[4:8]
            header_size = 8
            if atom_size == 1:
                extended_size = source.read(8)
                if len(extended_size) != 8:
                    return False
                atom_size = int.from_bytes(extended_size, "big")
                header_size = 16
            elif atom_size == 0:
                atom_size = size - position
            if atom_size < header_size:
                return False
            if atom_name == b"moov":
                moov_position = position
            elif atom_name == b"mdat":
                mdat_position = position
            position += atom_size
    return moov_position is not None and mdat_position is not None and moov_position < mdat_position


def is_browser_compatible(path: Path, metadata: VideoMetadata | None = None) -> bool:
    if path.suffix.lower() != ".mp4":
        return False
    video = metadata or inspect_video(path)
    return (
        video.container == "mp4"
        and video.video_codec == "h264"
        and video.pixel_format == "yuv420p"
        and video.audio_codec in (None, "aac")
        and has_faststart_metadata(path)
    )


def convert_to_browser_mp4(
    source_path: Path,
    target_path: Path,
    progress_callback: Callable[[int], None] | None = None,
) -> Path:
    """Write a separate H.264/yuv420p/AAC fast-start playback copy."""
    executable = _ffmpeg_executable()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = target_path.with_name(
        f"{target_path.stem}.{uuid.uuid4().hex}.partial.mp4"
    )
    duration = inspect_video(source_path).duration_seconds
    command = [
        executable,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(source_path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-profile:v",
        "baseline",
        "-pix_fmt",
        "yuv420p",
        "-fps_mode",
        "passthrough",
        "-threads",
        "2",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-progress",
        "pipe:1",
        "-nostats",
        str(temporary_path),
    ]

    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        output_tail: list[str] = []
        assert process.stdout is not None
        for line in process.stdout:
            output_tail.append(line.rstrip())
            output_tail = output_tail[-20:]
            if progress_callback and duration and duration > 0:
                timestamp_match = re.match(r"out_time_(?:us|ms)=(\d+)", line.strip())
                if timestamp_match:
                    microseconds = int(timestamp_match.group(1))
                    percent = min(99, max(0, round(microseconds / (duration * 1_000_000) * 100)))
                    progress_callback(percent)
        return_code = process.wait()
        if return_code != 0:
            details = "\n".join(output_tail)
            raise PlaybackPreparationError(
                "FFmpeg could not decode or transcode this video."
                + (f" {details}" if details else "")
            )
        metadata = inspect_video(temporary_path)
        if not is_browser_compatible(temporary_path, metadata):
            raise PlaybackPreparationError(
                "FFmpeg produced a file that failed browser-playback validation."
            )
        os.replace(temporary_path, target_path)
        if progress_callback:
            progress_callback(100)
        return target_path
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlaybackPreparationError("FFmpeg conversion could not be completed.") from exc
    finally:
        temporary_path.unlink(missing_ok=True)


class VideoPlaybackJobManager:
    """Prepare and cache per-video playback sources without changing uploads."""

    def __init__(self) -> None:
        self._jobs: dict[str, PlaybackJobState] = {}
        self._lock = RLock()
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="video-playback")

    def _set(self, video_id: str, state: PlaybackJobState) -> PlaybackJobState:
        with self._lock:
            self._jobs[video_id] = state
            return state

    def get_status(self, video_id: str) -> PlaybackJobState:
        with self._lock:
            return self._jobs.get(
                video_id,
                PlaybackJobState("not_started", 0, "Playback preparation has not started."),
            )

    def get_ready_path(self, video_id: str) -> Path | None:
        state = self.get_status(video_id)
        if state.status == "ready" and state.path and state.path.is_file():
            return state.path
        return None

    def prepare(
        self,
        video_id: str,
        source_path: Path,
        playback_dir: Path,
    ) -> PlaybackJobState:
        previous = self.get_status(video_id)
        if previous.status == "converting":
            return previous

        output_path = playback_dir / f"{video_id}.mp4"
        try:
            source_metadata = inspect_video(source_path)
            if is_browser_compatible(source_path, source_metadata):
                return self._set(
                    video_id,
                    PlaybackJobState(
                        "ready",
                        100,
                        "The original MP4 already meets browser playback requirements.",
                        source_path,
                    ),
                )
            if output_path.is_file() and is_browser_compatible(output_path):
                return self._set(
                    video_id,
                    PlaybackJobState(
                        "ready",
                        100,
                        "A compatible playback copy is already available.",
                        output_path,
                    ),
                )
        except (FfmpegUnavailableError, PlaybackPreparationError, OSError) as exc:
            logger.warning("Video playback inspection failed for %s: %s", video_id, exc)
            return self._set(
                video_id,
                PlaybackJobState("failed", 0, f"{exc} Annotated frame navigation remains available."),
            )

        with self._lock:
            current = self._jobs.get(video_id)
            if current and current.status == "converting":
                return current
            self._jobs[video_id] = PlaybackJobState(
                "converting",
                0,
                "Converting a browser-compatible playback copy.",
            )
        self._executor.submit(self._convert_job, video_id, source_path, output_path)
        return self.get_status(video_id)

    def _convert_job(self, video_id: str, source_path: Path, output_path: Path) -> None:
        def update_progress(percent: int) -> None:
            with self._lock:
                current = self._jobs.get(video_id)
                if current and current.status == "converting":
                    self._jobs[video_id] = replace(
                        current,
                        progress=max(current.progress, min(99, percent)),
                        message="Converting a browser-compatible playback copy.",
                    )

        try:
            converted_path = convert_to_browser_mp4(source_path, output_path, update_progress)
            self._set(
                video_id,
                PlaybackJobState(
                    "ready",
                    100,
                    "The browser-compatible playback copy is prepared.",
                    converted_path,
                ),
            )
        except (FfmpegUnavailableError, PlaybackPreparationError, OSError) as exc:
            logger.exception("Video playback conversion failed for %s", video_id)
            self._set(
                video_id,
                PlaybackJobState(
                    "failed",
                    0,
                    f"{exc} Annotated frame navigation remains available.",
                ),
            )


video_playback_jobs = VideoPlaybackJobManager()
