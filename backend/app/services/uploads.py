"""Product photo uploads. Files are checked by their actual bytes, not by the name or the
browser's claimed type, and saved under a random name."""
import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
MAX_BYTES = 2 * 1024 * 1024  # 2 MB

SIGNATURES = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}


def _detect(head: bytes) -> str | None:
    for sig, ext in SIGNATURES.items():
        if head.startswith(sig):
            return ext
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"
    return None


async def save_image(file: UploadFile) -> str:
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Photos must be 2 MB or smaller")
    ext = _detect(data[:16])
    if ext is None:
        raise HTTPException(415, "Upload a JPG, PNG or WebP photo")
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = secrets.token_hex(16) + ext
    (UPLOAD_DIR / name).write_bytes(data)
    return f"/uploads/{name}"
