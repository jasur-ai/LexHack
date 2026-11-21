"""Server-side image quality gate (§5.1): blur, brightness, contrast, skew, resolution, and glare blob detection."""

from __future__ import annotations

import io
import math
from typing import Any

from PIL import Image, ImageFilter, ImageStat

from app.config import get_settings
from app.engines.recognition.types import QualityMetrics

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False
    cv2 = None  # type: ignore
    np = None  # type: ignore


def _glare_blob_ratio_cv2(gray: Any) -> float:
    mask = (gray > 250).astype(np.uint8)
    total = gray.shape[0] * gray.shape[1]
    if total == 0:
        return 0.0
    num_labels, _labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    blob_pixels = 0
    # Only count connected bright blobs >= 25 pixels to ignore single-pixel specular noise
    for i in range(1, num_labels):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area >= 25:
            blob_pixels += area
    return blob_pixels / float(total)


def _skew_angle_cv2(gray: Any) -> float:
    edges = cv2.Canny(gray, 50, 150, apertureSize=3)
    lines = cv2.HoughLinesP(edges, 1, math.pi / 180.0, threshold=80, minLineLength=60, maxLineGap=10)
    if lines is None or len(lines) == 0:
        return 0.0
    angles: list[float] = []
    for line in lines[:80]:
        x1, y1, x2, y2 = line[0]
        ang = math.degrees(math.atan2(y2 - y1, x2 - x1))
        if -45.0 <= ang <= 45.0:
            angles.append(ang)
    if not angles:
        return 0.0
    angles.sort()
    return float(abs(angles[len(angles) // 2]))


def assess_image_quality(image_bytes: bytes) -> QualityMetrics:
    """Evaluate image quality metrics and return i18n warning keys (`rec.warn.*`)."""
    cfg = get_settings()
    try:
        with Image.open(io.BytesIO(image_bytes)) as img:
            w, h = img.size
            res_min = min(w, h)
            # Downscale longest edge to 1000 px for deterministic Laplacian scale
            scale = min(1.0, 1000.0 / float(max(w, h, 1)))
            nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
            gray_pil = img.convert("L").resize((nw, nh))
    except Exception:
        return QualityMetrics(ok=False, rejected=True, warnings=["rec.warn.invalid_image"])

    if _HAS_CV2:
        gray = np.array(gray_pil, dtype=np.uint8)
        blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        brightness = float(gray.mean())
        contrast = float(gray.std())
        glare_ratio = _glare_blob_ratio_cv2(gray)
        skew_deg = _skew_angle_cv2(gray)
    else:
        # Pure-Pillow fallback when OpenCV is absent
        stat = ImageStat.Stat(gray_pil)
        brightness = float(stat.mean[0])
        contrast = float(stat.stddev[0])
        lap = gray_pil.filter(ImageFilter.Kernel((3, 3), [0, 1, 0, 1, -4, 1, 0, 1, 0], scale=1, offset=128))
        # Pillow leaves the 1-px border unfiltered (raw pixel values); exclude it or flat images look "sharp".
        if lap.size[0] > 2 and lap.size[1] > 2:
            lap = lap.crop((1, 1, lap.size[0] - 1, lap.size[1] - 1))
        lap_stat = ImageStat.Stat(lap)
        blur = float(lap_stat.var[0])
        hist = gray_pil.histogram()
        total_px = max(1, gray_pil.size[0] * gray_pil.size[1])
        glare_ratio = sum(hist[251:256]) / float(total_px)
        skew_deg = 0.0

    warnings: list[str] = []
    rejected = False

    if blur < cfg.quality_blur_warn:
        warnings.append("rec.warn.blurry")
        rejected = True
    elif blur < cfg.quality_blur_ok:
        warnings.append("rec.warn.blurry")

    if brightness < cfg.quality_brightness_min or contrast < cfg.quality_contrast_min:
        warnings.append("rec.warn.dark")

    if brightness > cfg.quality_brightness_max or glare_ratio > cfg.quality_max_glare_ratio:
        warnings.append("rec.warn.glare")

    if res_min < cfg.quality_min_resolution:
        warnings.append("rec.warn.small")

    if skew_deg > cfg.quality_max_skew_deg:
        warnings.append("rec.warn.skewed")

    return QualityMetrics(
        blur=round(blur, 2),
        brightness=round(brightness, 2),
        contrast=round(contrast, 2),
        skew_deg=round(skew_deg, 2),
        resolution_min=res_min,
        glare_ratio=round(glare_ratio, 4),
        ok=(len(warnings) == 0),
        rejected=rejected,
        warnings=list(dict.fromkeys(warnings)),
    )
