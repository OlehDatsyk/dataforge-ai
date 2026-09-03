"""
DataForge AI - Security helpers.
No eval(), no exec(), no arbitrary code execution, no path traversal.
"""
import re
import uuid
from pathlib import Path

from backend.config import settings

_SAFE_CHARS = re.compile(r"[^A-Za-z0-9_.\-]")


def sanitize_filename(filename: str) -> str:
    """Strip directories and dangerous characters from a user-supplied filename."""
    name = Path(filename).name  # drop any directory components
    name = _SAFE_CHARS.sub("_", name)
    if not name or name in (".", ".."):
        name = "upload"
    return name[:150]


def generate_stored_name(original_filename: str) -> str:
    """Generate a collision-proof, path-safe filename for disk storage."""
    safe = sanitize_filename(original_filename)
    suffix = Path(safe).suffix.lower()
    return f"{uuid.uuid4().hex}{suffix}"


def safe_join(base_dir: Path, filename: str) -> Path:
    """Join a filename to a base directory, guaranteeing the result stays inside base_dir."""
    candidate = (base_dir / filename).resolve()
    base_resolved = base_dir.resolve()
    if base_resolved not in candidate.parents and candidate != base_resolved:
        raise ValueError("Invalid path: potential path traversal detected")
    return candidate


def validate_extension(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type '{ext or 'unknown'}'. "
            f"Supported types: {', '.join(sorted(settings.ALLOWED_EXTENSIONS))}"
        )
    return ext


def validate_size(size_bytes: int) -> None:
    if size_bytes <= 0:
        raise ValueError("The uploaded file is empty.")
    if size_bytes > settings.MAX_UPLOAD_SIZE_BYTES:
        raise ValueError(
            f"File exceeds the maximum upload size of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )
