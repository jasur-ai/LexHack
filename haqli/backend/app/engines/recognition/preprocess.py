"""Image & PDF preprocessing (§5.2): EXIF strip, orientation, page warp, ±15° deskew, CLAHE + adaptive threshold, 2600px cap."""

from __future__ import annotations

import importlib.util
import io
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps
from pypdf import PdfReader

from app.config import get_settings

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore

    _HAS_CV2 = True
except Exception:
    _HAS_CV2 = False
    cv2 = None  # type: ignore
    np = None  # type: ignore


@dataclass
class PreprocessedDocument:
    """Output of preprocessing: either extracted PDF text layers, or prepared image variants for OCR."""

    text_pages: list[str] = field(default_factory=list)
    image_variants: list[Any] = field(default_factory=list)  # list[np.ndarray | PIL.Image]
    page_count: int = 1
    used_text_layer: bool = False


def _order_quad_points(pts: Any) -> Any:
    rect = np.zeros((4, 2), dtype="float32")
    s = pts.sum(axis=1)
    rect[0] = pts[np.argmin(s)]
    rect[2] = pts[np.argmax(s)]
    diff = np.diff(pts, axis=1)
    rect[1] = pts[np.argmin(diff)]
    rect[3] = pts[np.argmax(diff)]
    return rect


def _perspective_crop_cv2(img: Any) -> Any:
    h, w = img.shape[:2]
    area_img = float(h * w)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:5]

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
        if len(approx) == 4 and cv2.contourArea(approx) > area_img * 0.35:
            rect = _order_quad_points(approx.reshape(4, 2))
            (tl, tr, br, bl) = rect
            max_w = int(max(np.linalg.norm(br - bl), np.linalg.norm(tr - tl)))
            max_h = int(max(np.linalg.norm(tr - br), np.linalg.norm(tl - bl)))
            if max_w < 300 or max_h < 300:
                return img
            dst = np.array([[0, 0], [max_w - 1, 0], [max_w - 1, max_h - 1], [0, max_h - 1]], dtype="float32")
            m = cv2.getPerspectiveTransform(rect, dst)
            return cv2.warpPerspective(img, m, (max_w, max_h))
    return img


def _deskew_cv2(img: Any) -> Any:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 100:
        return img
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle
    if abs(angle) < 0.5 or abs(angle) > 15.0:
        return img
    h, w = img.shape[:2]
    m = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    return cv2.warpAffine(img, m, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)


def _auto_rotate_osd(pil_img: Image.Image) -> Image.Image:
    if importlib.util.find_spec("pytesseract") is None:
        return pil_img
    try:
        import pytesseract

        osd = pytesseract.image_to_osd(pil_img)
        for line in osd.splitlines():
            if line.startswith("Rotate:"):
                deg = int(line.split(":", 1)[1].strip())
                if deg in (90, 180, 270):
                    return pil_img.rotate(-deg, expand=True)
    except Exception:
        pass
    return pil_img


def preprocess_image_bytes(image_bytes: bytes, *, low_contrast: bool = False) -> list[Any]:
    """Return 1 or 2 preprocessed image variants (CLAHE + optional adaptive threshold), longest edge <= 2600 px."""
    with Image.open(io.BytesIO(image_bytes)) as raw:
        img = ImageOps.exif_transpose(raw).convert("RGB")

    img = _auto_rotate_osd(img)

    # Cap longest edge to 2600 px
    w, h = img.size
    longest = max(w, h)
    if longest > 2600:
        scale = 2600.0 / float(longest)
        img = img.resize((int(w * scale), int(h * scale)), Image.Resampling.LANCZOS)

    if not _HAS_CV2:
        variants: list[Any] = [img]
        if low_contrast:
            variants.append(ImageOps.autocontrast(img.convert("L")).convert("RGB"))
        return variants

    bgr = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    bgr = _perspective_crop_cv2(bgr)
    bgr = _deskew_cv2(bgr)

    # CLAHE on L channel
    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l_ch, a_ch, b_ch = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    cl = clahe.apply(l_ch)
    enhanced = cv2.cvtColor(cv2.merge((cl, a_ch, b_ch)), cv2.COLOR_LAB2BGR)

    variants_cv: list[Any] = [enhanced]
    if low_contrast:
        gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        adaptive = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 21, 10)
        variants_cv.append(cv2.cvtColor(adaptive, cv2.COLOR_GRAY2BGR))
    return variants_cv


def preprocess_pdf_bytes(pdf_bytes: bytes) -> PreprocessedDocument:
    """Extract text layers via pypdf; rasterize pages with < 40 chars via pypdfium2 at 200 dpi (§5.2)."""
    cfg = get_settings()
    reader = PdfReader(io.BytesIO(pdf_bytes))
    num_pages = min(len(reader.pages), cfg.max_pdf_pages)
    text_pages: list[str] = []
    raster_indices: list[int] = []

    for idx in range(num_pages):
        txt = (reader.pages[idx].extract_text() or "").strip()
        text_pages.append(txt)
        if len(txt) < 40:
            raster_indices.append(idx)

    variants: list[Any] = []
    if raster_indices and importlib.util.find_spec("pypdfium2") is not None:
        try:
            import pypdfium2 as pdfium  # type: ignore

            pdf = pdfium.PdfDocument(pdf_bytes)
            for idx in raster_indices:
                page = pdf[idx]
                bitmap = page.render(scale=200.0 / 72.0)
                pil_img = bitmap.to_pil()
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                variants.extend(preprocess_image_bytes(buf.getvalue()))
        except Exception:
            pass

    return PreprocessedDocument(
        text_pages=text_pages,
        image_variants=variants,
        page_count=num_pages,
        used_text_layer=(len(raster_indices) < num_pages),
    )
