"""ReportLab A4 PDF generator (§13) with Unicode Cyrillic fonts (Ў Қ Ғ Ҳ), QR verification, and Ed25519 seal."""

from __future__ import annotations

import hashlib
import io
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import qrcode
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.config import get_settings
from app.engines.translit import localize_text

REQUIRED_GLYPHS = "O'zbekiston Ўзбекистон Қонун Ғоя Ҳуқуқ АБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
UZ_TZ = timezone(timedelta(hours=5))

_FONT_REG = "HaqliSans"
_FONT_BOLD = "HaqliSans-Bold"
_FONT_INITIALIZED = False
_RESOLVED_FONT_PATH = ""

_CANDIDATE_REGULAR = [
    Path(__file__).resolve().parent / "fonts" / "NotoSans-Regular.ttf",
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("C:/Windows/Fonts/segoeui.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
]
_CANDIDATE_BOLD = [
    Path(__file__).resolve().parent / "fonts" / "NotoSans-Bold.ttf",
    Path("C:/Windows/Fonts/arialbd.ttf"),
    Path("C:/Windows/Fonts/segoeuib.ttf"),
    Path("/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def _ensure_fonts() -> tuple[str, str]:
    global _FONT_INITIALIZED, _RESOLVED_FONT_PATH
    if _FONT_INITIALIZED:
        return _FONT_REG, _FONT_BOLD

    reg_path = next((p for p in _CANDIDATE_REGULAR if p.exists()), None)
    bold_path = next((p for p in _CANDIDATE_BOLD if p.exists()), reg_path)

    if reg_path is not None:
        pdfmetrics.registerFont(TTFont(_FONT_REG, str(reg_path)))
        pdfmetrics.registerFont(TTFont(_FONT_BOLD, str(bold_path or reg_path)))
        _RESOLVED_FONT_PATH = str(reg_path)
        _FONT_INITIALIZED = True
        return _FONT_REG, _FONT_BOLD

    # Fallback to built-in Helvetica only if zero TTF fonts exist on host
    _RESOLVED_FONT_PATH = "builtin:Helvetica"
    _FONT_INITIALIZED = True
    return "Helvetica", "Helvetica-Bold"


def check_font_glyph_coverage() -> dict[str, Any]:
    """Verify that the active PDF font covers Latin and Uzbek Cyrillic (Ў Қ Ғ Ҳ) glyphs."""
    reg_name, _ = _ensure_fonts()
    if reg_name == "Helvetica":
        return {"ok": False, "font_name": reg_name, "font_path": _RESOLVED_FONT_PATH, "missing_glyphs": list("ЎҚҒҲ")}
    font = pdfmetrics.getFont(reg_name)
    cmap = getattr(font.face, "charToGlyph", {}) or {}
    missing = [ch for ch in sorted(set(REQUIRED_GLYPHS)) if ch.strip() and ord(ch) not in cmap]
    return {
        "ok": len(missing) == 0,
        "font_name": reg_name,
        "font_path": _RESOLVED_FONT_PATH,
        "missing_glyphs": missing,
    }


def _make_qr_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(box_size=5, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0B1220", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _esc_xml(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def render_haqli_pdf(
    *,
    doc_id: str,
    title: str,
    subtitle: str,
    body_paragraphs: list[str],
    table_rows: list[list[str]] | None = None,
    doc_hash: str,
    seal_signature: str,
    needs_review: bool = True,
    locale: str = "uz_lat",
    output_path: Path | None = None,
) -> bytes:
    """Render an A4 Haqli legal PDF with 20mm margins, verification QR, Ed25519 seal & honest e-confirmation footer."""
    cfg = get_settings()
    reg_font, bold_font = _ensure_fonts()
    verify_url = f"{cfg.public_base_url.rstrip('/')}/v/{doc_id}"
    qr_img = ImageReader(io.BytesIO(_make_qr_bytes(verify_url)))
    issue_dt = datetime.now(UZ_TZ).strftime("%Y-%m-%d %H:%M UTC+5")
    short_hash = doc_hash[:16]

    e_confirm_note = localize_text(
        "Eslatma: Telegram tasdig'i va SHA-256/Ed25519 muhr oddiy elektron tasdiq bo'lib, malakali ERIs (ETsP) yoki notarial tasdiq o'rnini bosmaydi.",
        locale,
        "Примечание: подтверждение в Telegram и печать SHA-256/Ed25519 являются простым электронным подтверждением, не заменяющим квалифицированную ЭЦП или нотариуса.",
    )
    review_note = (
        localize_text(
            "Ogohlantirish: Hujjatda yuridik tekshiruvdan o'tmagan (needs_review) normativ ma'lumotlar mavjud.",
            locale,
            "Предупреждение: Документ ссылается на нормативные данные со статусом «Не проверено юристом».",
        )
        if needs_review
        else ""
    )

    def _draw_page_chrome(canvas, doc):
        canvas.saveState()
        # Embed HaqliDocId & HaqliSeal in PDF Info metadata (§8)
        canvas.setAuthor("haqli")
        canvas.setTitle(title)
        canvas.setSubject(f"HaqliDocId={doc_id};HaqliSeal={seal_signature}")
        canvas.setKeywords(f"HaqliDocId:{doc_id} HaqliSeal:{seal_signature}")
        w, h = A4
        # Top thin teal rule
        canvas.setStrokeColor(colors.HexColor("#0F766E"))
        canvas.setLineWidth(1.5)
        canvas.line(20 * mm, h - 14 * mm, w - 20 * mm, h - 14 * mm)
        canvas.setFont(bold_font, 9)
        canvas.setFillColor(colors.HexColor("#0F766E"))
        canvas.drawString(20 * mm, h - 12 * mm, "haqli")
        canvas.setFont(reg_font, 8)
        canvas.setFillColor(colors.HexColor("#4A5568"))
        canvas.drawRightString(w - 20 * mm, h - 12 * mm, f"ID: {doc_id[:12]}  |  {issue_dt}")

        # Footer QR + Hash + Honest e-confirmation note
        canvas.setStrokeColor(colors.HexColor("#E3E8EF"))
        canvas.setLineWidth(0.8)
        canvas.line(20 * mm, 29 * mm, w - 20 * mm, 29 * mm)
        canvas.drawImage(qr_img, w - 38 * mm, 8 * mm, width=18 * mm, height=18 * mm)
        canvas.setFont(reg_font, 7)
        canvas.setFillColor(colors.HexColor("#4A5568"))
        canvas.drawString(20 * mm, 24 * mm, f"Verify: {verify_url}  |  SHA-256: {short_hash}  |  Seal: {seal_signature[:18]}…")
        canvas.drawString(20 * mm, 19 * mm, e_confirm_note[:108])
        if len(e_confirm_note) > 108:
            canvas.drawString(20 * mm, 15.5 * mm, e_confirm_note[108:215])
        if review_note:
            canvas.setFillColor(colors.HexColor("#B45309"))
            canvas.drawString(20 * mm, 11.5 * mm, review_note[:115])
        canvas.setFillColor(colors.HexColor("#4A5568"))
        canvas.drawString(20 * mm, 7.5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=22 * mm,
        bottomMargin=33 * mm,
    )

    styles = getSampleStyleSheet()
    st_title = ParagraphStyle("HTitle", parent=styles["Heading1"], fontName=bold_font, fontSize=14, leading=18, textColor=colors.HexColor("#14213D"), spaceAfter=4)
    st_sub = ParagraphStyle("HSub", parent=styles["Normal"], fontName=reg_font, fontSize=9.5, leading=13, textColor=colors.HexColor("#4A5568"), spaceAfter=10)
    st_body = ParagraphStyle("HBody", parent=styles["Normal"], fontName=reg_font, fontSize=10, leading=14.5, textColor=colors.HexColor("#0B1220"), spaceAfter=7)

    story: list[Any] = [
        Paragraph(_esc_xml(title), st_title),
        Paragraph(_esc_xml(subtitle), st_sub),
    ]
    for para in body_paragraphs:
        if para.strip():
            story.append(Paragraph(_esc_xml(para), st_body))

    if table_rows:
        story.append(Spacer(1, 4 * mm))
        tbl = Table(table_rows, colWidths=[70 * mm, 100 * mm])
        tbl.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (-1, 0), bold_font),
                    ("FONTNAME", (0, 1), (-1, -1), reg_font),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F0F3F8")),
                    ("TEXTCOLOR", (0, 0), (-1, -1), colors.HexColor("#0B1220")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(tbl)

    doc.build(story, onFirstPage=_draw_page_chrome, onLaterPages=_draw_page_chrome)
    pdf_bytes = buf.getvalue()

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)
    return pdf_bytes


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
