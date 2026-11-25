from dataclasses import dataclass
from pathlib import Path
import uuid

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

ALLOWED_VIDEO_EXTENSIONS: dict[str, str] = {
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
}

ISOBMFF_BOX_MARKERS = {b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot"}


@dataclass(frozen=True)
class SavedVideoFile:
    """Metadata produced after streaming and validating an uploaded video."""

    original_filename: str
    stored_filename: str
    file_path: str
    absolute_path: Path
    file_size: int
    mime_type: str


def _has_valid_video_signature(header: bytes, extension: str) -> bool:
    """Validate container magic bytes rather than trusting filename or MIME alone."""
    if len(header) < 12:
        return False

    if extension in {".mp4", ".mov"}:
        # ISO Base Media / QuickTime box header places the 4-byte atom type at bytes 4..8.
        return header[4:8] in ISOBMFF_BOX_MARKERS

    if extension == ".avi":
        return header[:4] == b"RIFF" and header[8:12] == b"AVI "

    return False


def _sanitize_original_filename(raw_name: str | None) -> str:
    """Strip directory components and ensure a non-empty filename."""
    cleaned = Path(raw_name or "").name.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid video filename is required.",
        )
    return cleaned[:255]


def cleanup_saved_file(file_path: Path | None) -> None:
    """Best-effort removal of a partial or orphaned upload file."""
    if file_path is None:
        return
    try:
        file_path.unlink(missing_ok=True)
    except OSError:
        pass


async def stream_and_validate_video(upload: UploadFile) -> SavedVideoFile:
    """Stream an uploaded video in chunks to storage/uploads while validating content and size."""
    settings = get_settings()
    original_filename = _sanitize_original_filename(upload.filename)
    extension = Path(original_filename).suffix.lower()

    if extension not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported video format. Allowed extensions are MP4, MOV, and AVI.",
        )

    canonical_mime = ALLOWED_VIDEO_EXTENSIONS[extension]
    upload_dir = settings.resolved_upload_dir
    stored_filename = f"{uuid.uuid4().hex}{extension}"
    destination = upload_dir / stored_filename

    total_bytes = 0
    header_checked = False
    max_bytes = settings.max_upload_size_bytes
    chunk_size = settings.upload_chunk_size_bytes

    try:
        with destination.open("wb") as out_file:
            while True:
                chunk = await upload.read(chunk_size)
                if not chunk:
                    break

                if not header_checked:
                    if not _has_valid_video_signature(chunk[:64], extension):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=(
                                "Invalid video file content. The uploaded file does not match a "
                                f"valid {extension.lstrip('.').upper()} container."
                            ),
                        )
                    header_checked = True

                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                        detail="Uploaded video exceeds the maximum allowed size of 500 MB.",
                    )

                out_file.write(chunk)

        if total_bytes == 0 or not header_checked:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Uploaded video file is empty.",
            )
    except HTTPException:
        cleanup_saved_file(destination)
        raise
    except OSError as exc:
        cleanup_saved_file(destination)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save uploaded video to storage.",
        ) from exc
    finally:
        await upload.close()

    project_root = Path(__file__).resolve().parents[3]
    try:
        relative_path = destination.relative_to(project_root).as_posix()
    except ValueError:
        relative_path = f"storage/uploads/{stored_filename}"

    return SavedVideoFile(
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_path=relative_path,
        absolute_path=destination,
        file_size=total_bytes,
        mime_type=canonical_mime,
    )
