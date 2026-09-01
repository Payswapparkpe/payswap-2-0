"""Render an agreement body to a final, immutable PDF for signing.

The bytes of this PDF are what get hashed (``Agreement.document_hash``),
uploaded to Cashfree eSign, and stored. Any content change must produce a new
Agreement row — signed PDFs are never regenerated in place.
"""

import hashlib
import io

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN = 20 * mm
LINE_HEIGHT = 5.4 * mm
FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
SIZE = 9.5


def _is_heading(text: str) -> bool:
    if text.startswith(("SCHEDULE", "SIGNATURES", "BY AND BETWEEN", "ANNEXURE", "Section", "Schedule")):
        return True
    if text.isupper() and len(text) < 90:
        return True
    first, _, rest = text.partition(" ")
    return first.rstrip(".").isdigit() and rest.isupper() and len(text) < 90


def render_agreement_pdf(*, title: str, reference: str, body: str) -> bytes:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    pdf.setTitle(title)
    pdf.setSubject(f"PayswapHub agreement {reference}")

    y = PAGE_HEIGHT - MARGIN
    page = 1

    def footer():
        pdf.setFont(FONT, 8)
        pdf.drawString(MARGIN, 12 * mm, f"{reference} · PayswapHub · digitally generated")
        pdf.drawRightString(PAGE_WIDTH - MARGIN, 12 * mm, f"Page {page}")

    def new_page():
        nonlocal y, page
        footer()
        pdf.showPage()
        page += 1
        y = PAGE_HEIGHT - MARGIN

    pdf.setFont(FONT_BOLD, 14)
    pdf.drawString(MARGIN, y, title)
    y -= LINE_HEIGHT * 1.6

    for paragraph in body.split("\n"):
        text = paragraph.strip()
        if not text:
            y -= LINE_HEIGHT / 2
            continue
        heading = _is_heading(text)
        pdf.setFont(FONT_BOLD if heading else FONT, SIZE if not heading else 10.5)
        # naive word-wrap at ~95 chars for 9.5pt Helvetica on A4
        words = text.split()
        line = ""
        for word in words:
            candidate = f"{line} {word}".strip()
            if len(candidate) > 95:
                if y < MARGIN + LINE_HEIGHT:
                    new_page()
                    pdf.setFont(FONT_BOLD if heading else FONT, SIZE if not heading else 10.5)
                pdf.drawString(MARGIN, y, line)
                y -= LINE_HEIGHT
                line = word
            else:
                line = candidate
        if line:
            if y < MARGIN + LINE_HEIGHT:
                new_page()
                pdf.setFont(FONT_BOLD if heading else FONT, SIZE if not heading else 10.5)
            pdf.drawString(MARGIN, y, line)
            y -= LINE_HEIGHT

    footer()
    pdf.save()
    return buffer.getvalue()


def pdf_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
