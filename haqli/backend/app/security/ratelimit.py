"""Rate limiting, RFC 9457 problem+json responses, magic-byte upload sniffing, decompression-bomb guard & EXIF strip."""

from __future__ import annotations

import io
import time
from collections import defaultdict, deque

from fastapi.responses import JSONResponse
from PIL import Image, ImageOps

# Decompression-bomb guard (§11): cap at 40 MP
Image.MAX_IMAGE_PIXELS = 40_000_000

ALLOWED_UPLOAD_MIMES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "application/pdf",
    "audio/webm",
    "audio/ogg",
    "audio/mp4",
    "audio/mpeg",
    "audio/wav",
    "text/plain",
}

AUDIO_MIMES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"}
IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp", "image/heic"}


class SlidingWindowRateLimiter:
    """In-memory per-key sliding-window rate limiter."""

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        dq = self._buckets[key]
        cutoff = now - self.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()
        if len(dq) >= self.max_requests:
            return False
        dq.append(now)
        return True


def problem_response(
    *,
    status: int,
    title: str,
    detail: str,
    code: str,
    request_id: str = "",
    type_uri: str = "https://haqli.uz/errors",
) -> JSONResponse:
    """Return RFC 9457 problem+json payload."""
    return JSONResponse(
        status_code=status,
        media_type="application/problem+json",
        content={
            "type": f"{type_uri}/{code.lower()}",
            "title": title,
            "status": status,
            "detail": detail,
            "code": code,
            "request_id": request_id,
        },
    )


def sniff_magic_mime(data: bytes, filename: str = "") -> str:
    """Detect real file MIME type from magic bytes (never trust client Content-Type header alone)."""
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    if len(data) >= 12 and data[4:8] == b"ftyp":
        brand = data[8:12]
        if brand in (b"heic", b"heix", b"mif1", b"msf1"):
            return "image/heic"
        return "audio/mp4"
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    if data.startswith(b"\x1a\x45\xdf\xa3"):
        return "audio/webm"
    if data.startswith(b"OggS"):
        return "audio/ogg"
    if data.startswith(b"ID3") or data[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    if filename.lower().endswith((".txt", ".md")):
        return "text/plain"
    return "application/octet-stream"


def validate_image_dimensions(data: bytes, max_megapixels: int = 40) -> tuple[bool, str | None]:
    """Check pixel dimensions safely without decoding malicious decompression bombs (§9, §11)."""
    prev_max = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = max_megapixels * 1_000_000
    try:
        with Image.open(io.BytesIO(data)) as img:
            w, h = img.size
            if w * h > max_megapixels * 1_000_000:
                return False, f"Image exceeds {max_megapixels} MP limit ({w}x{h})."
        return True, None
    except Image.DecompressionBombError:
        return False, "Decompression bomb detected: image dimensions exceed safety limit."
    except Exception as exc:
        return False, f"Invalid image file: {exc}"
    finally:
        Image.MAX_IMAGE_PIXELS = prev_max


def strip_image_exif(data: bytes, mime: str) -> bytes:
    """Apply EXIF orientation and re-encode JPEG/PNG/WebP via Pillow to strip EXIF/GPS metadata (§5.2, §11)."""
    if mime not in ("image/jpeg", "image/png", "image/webp"):
        return data
    try:
        with Image.open(io.BytesIO(data)) as img:
            oriented = ImageOps.exif_transpose(img)
            out = io.BytesIO()
            fmt = "JPEG" if mime == "image/jpeg" else ("WEBP" if mime == "image/webp" else "PNG")
            if fmt == "JPEG" and oriented.mode in ("RGBA", "P", "LA"):
                oriented = oriented.convert("RGB")
            clean = Image.new(oriented.mode, oriented.size)
            clean.putdata(list(oriented.getdata()))
            save_kwargs = {"quality": 88} if fmt in ("JPEG", "WEBP") else {}
            clean.save(out, format=fmt, **save_kwargs)
            return out.getvalue()
    except Exception:
        return data
