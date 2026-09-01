"""Render a Purchase Order as a standard A4 PDF document.

The document is generated on demand from the current order revision, so it
always reflects the latest approved commercial content. Downloads are POST-only
and audited (see ``portals.views.common.OrderDocumentView``).
"""

import io
from decimal import Decimal

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from agreements.template import FIRST_PARTY
from orders.models import ApprovalDecision

PAGE_WIDTH, _ = A4
MARGIN = 16 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN

INK = colors.HexColor("#1c2733")
MUTED = colors.HexColor("#5b6a76")
LINE = colors.HexColor("#c9d3da")
HEAD_BG = colors.HexColor("#eef3f6")

H1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=15, textColor=INK, spaceAfter=1 * mm)
H2 = ParagraphStyle(
    "h2", fontName="Helvetica-Bold", fontSize=10, textColor=INK, spaceBefore=3 * mm, spaceAfter=1.5 * mm
)
BODY = ParagraphStyle("body", fontName="Helvetica", fontSize=9, leading=12.5, textColor=INK)
SMALL = ParagraphStyle("small", parent=BODY, fontSize=8, leading=11, textColor=MUTED)
CELL = ParagraphStyle("cell", parent=BODY, fontSize=8.5, leading=11.5)
CELL_R = ParagraphStyle("cell_r", parent=CELL, alignment=2)

PO_TERMS = [
    "This Purchase Order is issued under and governed by the Voucher Supply Agreement executed between the Buyer and Payswap Fintech Private Limited. In case of conflict, the Agreement prevails.",
    "This Purchase Order records the approved commercial request. Settlement and delivery are handled outside this approval workflow as agreed between the parties.",
    "Prices are in Indian Rupees (INR). Voucher denominations are charged at face value. Goods and Services Tax (GST) at 18% applies to the service fee only and is shown separately.",
    "Brand vouchers are subject to the issuing brand's terms and conditions. The Buyer shall not resell vouchers on public marketplaces or use them for prohibited or unlawful purposes.",
    "Any discrepancy must be reported promptly after approval. Cancellation after approval is subject to the Agreement and the platform cancellation policy.",
    "This Purchase Order is not transferable. Any amendment creates a new revision and requires re-approval.",
    "Jurisdiction: courts at Jaipur, Rajasthan, India, subject to the dispute-resolution clause of the Agreement. Governed by the laws of India.",
    "This is a computer-generated document and does not require a physical signature.",
]

_ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _two_digit(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, rest = divmod(n, 10)
    return f"{_TENS[tens]} {_ONES[rest]}".strip()


def _three_digit(n: int) -> str:
    hundreds, rest = divmod(n, 100)
    parts = []
    if hundreds:
        parts.append(f"{_ONES[hundreds]} Hundred")
    if rest:
        parts.append(_two_digit(rest))
    return " ".join(parts)


def amount_in_words(amount: Decimal) -> str:
    """Indian numbering: Rupees … Lakh … Crore, with paise. Compliance convention
    for Indian commercial documents (total must be stated in words)."""
    rupees = int(amount)
    paise = int((amount - rupees) * 100)
    if rupees == 0 and paise == 0:
        return "Rupees Zero Only"
    words = []
    crores, rupees = divmod(rupees, 10_000_000)
    lakhs, rupees = divmod(rupees, 100_000)
    thousands, rest = divmod(rupees, 1_000)
    if crores:
        words.append(f"{_three_digit(crores)} Crore")
    if lakhs:
        words.append(f"{_two_digit(lakhs)} Lakh")
    if thousands:
        words.append(f"{_two_digit(thousands)} Thousand")
    if rest:
        words.append(_three_digit(rest))
    result = "Rupees " + " ".join(words) if words else ""
    if paise:
        result = f"{result} and {_two_digit(paise)} Paise" if result else f"{_two_digit(paise)} Paise"
    return f"{result} Only".strip()


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def _safe(text: str) -> str:
    """The PDF base fonts (Helvetica) have no rupee glyph (U+20B9); it renders as
    a box. Use "Rs." in generated documents — the web UI keeps the ₹ symbol."""
    return str(text).replace("₹", "Rs. ")


def _party_block(title: str, lines: list[str]) -> Table:
    rows = [[Paragraph(f"<b>{title}</b>", CELL)]]
    rows += [[Paragraph(_safe(line), CELL)] for line in lines if line]
    table = Table(rows, colWidths=[CONTENT_WIDTH / 2 - 2 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("BACKGROUND", (0, 0), (0, 0), HEAD_BG),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
            ]
        )
    )
    return table


def po_document_context(order) -> dict:
    """All display strings that go onto the purchase order. Kept separate from
    the PDF renderer so the complete field set is unit-testable without parsing
    PDF bytes."""
    from agreements.template import merchant_party_context  # deferred: decrypts KYC data

    merchant = order.merchant
    buyer = merchant_party_context(merchant)
    approval = (
        ApprovalDecision.objects.filter(order=order, action=ApprovalDecision.Action.APPROVE)
        .select_related("actor", "revision")
        .first()
    )
    agreement = merchant.agreements.order_by("-created_at").first()
    return {
        "po_number": order.public_id,
        "po_date": order.created_at.strftime("%d %b %Y"),
        "revision": order.revision,
        "status": order.get_status_display(),
        "currency": "INR",
        "agreement_ref": agreement.public_id if agreement else "Pending execution",
        "company_gstin": getattr(settings, "COMPANY_GSTIN", "") or "As registered",
        "company_pan": getattr(settings, "COMPANY_PAN", "") or "As registered",
        "hsn": getattr(settings, "COMPANY_VOUCHER_HSN", "4907"),
        "buyer": buyer,
        "product_name": order.product.name,
        "brand_name": order.product.brand.name,
        "denomination": order.unit_value,
        "quantity": order.quantity,
        "subtotal": order.subtotal,
        "fees": order.fees,
        "fee_percent": f"{order.product.fee_rate * 100:.2f}",
        "tax": order.tax,
        "total": order.total,
        "total_words": amount_in_words(order.total),
        "created_by": order.submitted_by.name or order.submitted_by.email,
        "approved_line": (
            f"Approved by: {approval.actor.name or approval.actor.email} on "
            f"{approval.created_at.strftime('%d %b %Y, %I:%M %p')} (revision {approval.revision.revision})"
            if approval
            else "Approval: pending"
        ),
        "generated_on": timezone.localtime().strftime("%d %b %Y, %I:%M %p IST"),
        "terms": PO_TERMS,
    }


def render_po_pdf(order) -> bytes:
    """Standard A4 purchase order: parties, PO metadata, item table, totals with
    amount in words, terms and conditions, and authorization block."""
    ctx = po_document_context(order)
    buyer = ctx["buyer"]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=16 * mm,
        title=f"Purchase Order {ctx['po_number']}",
        subject=f"PayswapHub purchase order {ctx['po_number']} revision {ctx['revision']}",
    )

    story = []
    story.append(
        Paragraph("PURCHASE ORDER", ParagraphStyle("title", parent=H1, alignment=1, spaceAfter=2 * mm))
    )

    meta = Table(
        [
            [
                Paragraph(
                    f"<b>{FIRST_PARTY['legal_name']}</b><br/>{FIRST_PARTY['office']}<br/>"
                    f"GSTIN: {ctx['company_gstin']} · PAN: {ctx['company_pan']}<br/>{FIRST_PARTY['email']}",
                    CELL,
                ),
                Paragraph(
                    f"<b>PO Number:</b> {ctx['po_number']}<br/>"
                    f"<b>PO Date:</b> {ctx['po_date']}<br/>"
                    f"<b>Revision:</b> {ctx['revision']} · <b>Status:</b> {ctx['status']}<br/>"
                    f"<b>Currency:</b> {ctx['currency']}<br/>"
                    f"<b>Agreement ref:</b> {ctx['agreement_ref']}",
                    CELL,
                ),
            ]
        ],
        colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
    )
    meta.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta)
    story.append(Spacer(1, 2 * mm))

    supplier = _party_block(
        "Supplier (From)",
        [
            FIRST_PARTY["legal_name"],
            FIRST_PARTY["office"],
            f"GSTIN: {ctx['company_gstin']} · PAN: {ctx['company_pan']}",
            f"Contact: {FIRST_PARTY['email']}",
        ],
    )
    bill_to = _party_block(
        "Buyer (Bill To)",
        [
            f"{buyer['legal_name']} (Merchant ID {buyer['merchant_id']})",
            buyer["office"],
            f"GSTIN: {buyer['gstin']} · PAN: {buyer['pan']}",
            f"Contact: {buyer['email']} · {buyer['mobile']}",
            f"Signatory: {buyer['signatory_name']} ({buyer['signatory_designation']})",
        ],
    )
    parties = Table([[supplier, bill_to]], colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2])
    parties.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(parties)

    story.append(Paragraph("Order items", H2))
    items = Table(
        [
            ["#", "Description", "HSN/SAC", "Denomination (Rs.)", "Qty", "Amount (Rs.)"],
            [
                "1",
                Paragraph(
                    f"{_safe(ctx['product_name'])} — brand voucher issued by {_safe(ctx['brand_name'])}",
                    CELL,
                ),
                ctx["hsn"],
                Paragraph(_money(ctx["denomination"]), CELL_R),
                Paragraph(str(ctx["quantity"]), CELL_R),
                Paragraph(_money(ctx["subtotal"]), CELL_R),
            ],
        ],
        colWidths=[9 * mm, 78 * mm, 18 * mm, 25 * mm, 12 * mm, 28 * mm],
    )
    items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), HEAD_BG),
                ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8.5),
                ("FONT", (0, 1), (-1, -1), "Helvetica", 8.5),
                ("GRID", (0, 0), (-1, -1), 0.5, LINE),
                ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    story.append(items)

    totals_rows = [
        ["Subtotal (voucher face value)", _money(ctx["subtotal"])],
        [f"Service fee ({ctx['fee_percent']}% of face value)", _money(ctx["fees"])],
        ["GST @ 18% on service fee", _money(ctx["tax"])],
        ["Grand total", _money(ctx["total"])],
    ]
    totals = Table(
        [[Paragraph(label, CELL), Paragraph(value, CELL_R)] for label, value in totals_rows],
        colWidths=[CONTENT_WIDTH - 40 * mm, 40 * mm],
    )
    totals.setStyle(
        TableStyle(
            [
                ("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 9),
                ("BACKGROUND", (0, -1), (-1, -1), HEAD_BG),
                ("LINEABOVE", (0, 0), (-1, 0), 0.6, LINE),
                ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
                ("TOPPADDING", (0, 0), (-1, -1), 2.5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(totals)
    story.append(Spacer(1, 1 * mm))
    story.append(Paragraph(f"<b>Amount in words:</b> {ctx['total_words']}", BODY))

    story.append(Paragraph("Commercial summary", H2))
    story.append(
        Paragraph(
            "<b>Status:</b> approved purchase order. "
            "<b>Settlement and delivery:</b> as agreed between the parties under the governing Agreement. "
            "<b>Validity:</b> brand terms apply to any voucher products listed above.",
            BODY,
        )
    )

    story.append(Paragraph("Terms and conditions", H2))
    for index, term in enumerate(ctx["terms"], start=1):
        story.append(Paragraph(f"{index}. {term}", SMALL))
        story.append(Spacer(1, 0.8 * mm))

    story.append(Paragraph("Authorization", H2))
    auth = Table(
        [
            [
                Paragraph(
                    f"<b>For the Buyer</b><br/><br/>Created by: {ctx['created_by']}<br/>{ctx['approved_line']}<br/><br/>"
                    f"Authorized Signatory: {buyer['signatory_name']}<br/>{buyer['signatory_designation']}",
                    CELL,
                ),
                Paragraph(
                    f"<b>For {FIRST_PARTY['legal_name']}</b><br/><br/><br/><br/>"
                    f"Authorized Signatory: {FIRST_PARTY['signatory_name']}<br/>{FIRST_PARTY['signatory_designation']}",
                    CELL,
                ),
            ]
        ],
        colWidths=[CONTENT_WIDTH / 2, CONTENT_WIDTH / 2],
    )
    auth.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOX", (0, 0), (0, 0), 0.6, LINE),
                ("BOX", (1, 0), (1, 0), 0.6, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(auth)

    def footer(pdf, _doc):
        pdf.saveState()
        pdf.setFont("Helvetica", 7.5)
        pdf.setFillColor(MUTED)
        pdf.drawString(
            MARGIN,
            10 * mm,
            f"{ctx['po_number']} · revision {ctx['revision']} · generated {ctx['generated_on']} · PayswapHub",
        )
        pdf.drawRightString(PAGE_WIDTH - MARGIN, 10 * mm, f"Page {pdf.getPageNumber()}")
        pdf.restoreState()

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()
