from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.pdf.utils import (
    BRAND_BLUE,
    BRAND_LIGHT_BLUE,
    DARK_TEXT,
    GREEN,
    MARGIN,
    RED,
    money,
)

HEADER_H = 1.05 * inch
PAGE_W, PAGE_H = letter

# Fixed diagram geometry (page 1) — positions never depend on text length
CIRCLE_R = 0.92 * inch
RESERVE_W = 2.1 * inch
RESERVE_H = 2.1 * inch
SHAPE_GAP = 0.4 * inch
DIAGRAM_Y = PAGE_H / 2 - 0.25 * inch

# Fixed slots for amounts inside shapes
AMOUNT_SLOT_W = 1.35 * inch
AMOUNT_FONT_MAX = 20
AMOUNT_FONT_MIN = 11


def generate_sacs_pdf(payload: dict) -> bytes:
    client = payload["client"]
    report = payload["report"]
    calc = payload["report"]["calculations"]["sacs"]

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    _draw_page1(c, width, height, client, report, calc)
    c.showPage()
    _draw_page2(c, width, height, client, report, calc)
    c.save()
    buffer.seek(0)
    return buffer.read()


def _layout_diagram(width: float) -> dict:
    """Fixed horizontal layout: Inflow | Outflow | Private Reserve."""
    left = MARGIN
    right = width - MARGIN
    content_w = right - left

    inflow_cx = left + CIRCLE_R
    outflow_cx = inflow_cx + CIRCLE_R + SHAPE_GAP + CIRCLE_R
    box_x = outflow_cx + CIRCLE_R + SHAPE_GAP
    used = box_x + RESERVE_W - left
    shift = max(0, (content_w - used) / 2)

    inflow_cx += shift
    outflow_cx += shift
    box_x += shift

    return {
        "inflow_cx": inflow_cx,
        "outflow_cx": outflow_cx,
        "box_x": box_x,
        "inflow_right": inflow_cx + CIRCLE_R,
        "outflow_left": outflow_cx - CIRCLE_R,
        "outflow_right": outflow_cx + CIRCLE_R,
        "box_left": box_x,
        "box_right": box_x + RESERVE_W,
    }


def _draw_header(c, width, height, client, report, *, subtitle: str | None = None):
    c.setFillColor(BRAND_BLUE)
    c.rect(0, height - HEADER_H, width, HEADER_H, fill=1, stroke=0)
    c.setFillColor(colors.white)

    title = subtitle or "Simple Automated Cash Flow (SACS)"
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, height - 0.52 * inch, title)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(MARGIN, height - 0.78 * inch, client["display_name"])

    date_label = report.get("report_date") or report.get("quarter_label", "")
    quarter = report.get("quarter_label", "")
    right_text = f"{quarter}  ·  {date_label}" if date_label and quarter != date_label else (quarter or date_label)
    c.setFont("Helvetica", 10)
    c.drawRightString(width - MARGIN, height - 0.78 * inch, right_text)


def _draw_page1(c, width, height, client, report, calc):
    _draw_header(c, width, height, client, report)
    layout = _layout_diagram(width)
    y = DIAGRAM_Y
    box_y = y - RESERVE_H / 2

    # Connectors (behind shapes)
    _draw_arrow_line(c, layout["inflow_right"], layout["outflow_left"], y)
    _draw_arrow_line(c, layout["outflow_right"], layout["box_left"], y)

    _draw_circle(
        c, layout["inflow_cx"], y, CIRCLE_R, GREEN,
        "Inflow", money(calc["inflow"]), "/ month",
    )
    _draw_circle(
        c, layout["outflow_cx"], y, CIRCLE_R, RED,
        "Outflow", money(calc["outflow"]), "/ month",
    )

    # Outflow "X" marker (expense deduction)
    c.setFillColor(RED)
    c.setFont("Helvetica-Bold", 11)
    c.drawCentredString(layout["outflow_cx"], y + CIRCLE_R * 0.55, "X")

    # Private Reserve — fixed internal slots
    c.setFillColor(BRAND_BLUE)
    c.roundRect(layout["box_x"], box_y, RESERVE_W, RESERVE_H, 14, fill=1, stroke=0)
    bx = layout["box_x"]
    slot_cx = bx + RESERVE_W / 2
    _draw_fixed_slot_text(c, slot_cx, box_y + RESERVE_H - 0.42 * inch, "Private Reserve", "Helvetica-Bold", 13)
    _draw_fixed_slot_text(c, slot_cx, box_y + RESERVE_H - 0.68 * inch, "Monthly Excess", "Helvetica", 10)
    _draw_fixed_slot_amount(
        c, slot_cx, box_y + RESERVE_H / 2 - 0.05 * inch, money(calc["excess"]), fill_color=colors.white
    )
    _draw_fixed_slot_text(c, slot_cx, box_y + 0.32 * inch, "Transferred monthly", "Helvetica", 9)

    c.setFillColor(BRAND_BLUE)
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, y - CIRCLE_R - 0.5 * inch, "Monthly Cashflow")


def _draw_page2(c, width, height, client, report, calc):
    _draw_header(c, width, height, client, report, subtitle="SACS — Account Details")

    schwab_label = client.get("schwab_label") or "Schwab Investment Account"
    cards = [
        ("Private Reserve Balance", calc["private_reserve_balance"]),
        (schwab_label, calc["schwab_balance"]),
        ("Target Savings (6× expenses + deductibles)", calc["private_reserve_target"]),
    ]

    card_h = 1.05 * inch
    card_w = width - 2 * MARGIN
    value_slot_right = width - MARGIN - 0.3 * inch
    title_left = MARGIN + 0.28 * inch
    title_max_w = card_w * 0.62

    card_top = height - HEADER_H - 0.55 * inch
    for title, value in cards:
        card_y = card_top - card_h
        c.setFillColor(colors.white)
        c.setStrokeColor(BRAND_BLUE)
        c.setLineWidth(1.2)
        c.roundRect(MARGIN, card_y, card_w, card_h, 8, fill=1, stroke=1)

        c.setFillColor(DARK_TEXT)
        _draw_wrapped_title(c, title_left, card_y + card_h - 0.38 * inch, title, title_max_w)

        value_y = card_y + 0.32 * inch
        c.setFillColor(BRAND_BLUE)
        _draw_fixed_slot_amount(c, value_slot_right, value_y, money(value), align="right")

        card_top = card_y - 0.28 * inch

    gap = calc["private_reserve_balance"] - calc["private_reserve_target"]
    status = "On Target" if gap >= 0 else "Below Target"
    direction = "above" if gap >= 0 else "below"
    c.setFont("Helvetica", 11)
    c.setFillColor(DARK_TEXT)
    c.drawString(
        MARGIN,
        card_top - 0.35 * inch,
        f"Status: {status} ({money(abs(gap))} {direction} target)",
    )


def _draw_circle(c, cx, cy, radius, fill_color, title, amount, suffix):
    c.setFillColor(fill_color)
    c.circle(cx, cy, radius, fill=1, stroke=0)
    c.setFillColor(colors.white)
    _draw_fixed_slot_text(c, cx, cy + radius * 0.42, title, "Helvetica-Bold", 12)
    _draw_fixed_slot_amount(c, cx, cy - radius * 0.05, amount, fill_color=colors.white)
    _draw_fixed_slot_text(c, cx, cy - radius * 0.38, suffix, "Helvetica", 9)


def _draw_fixed_slot_amount(c, x, y, text, align="center", fill_color=None):
    """Draw amount in a fixed-width slot; shrink font only, never move anchor."""
    size = AMOUNT_FONT_MAX
    while size >= AMOUNT_FONT_MIN and stringWidth(text, "Helvetica-Bold", size) > AMOUNT_SLOT_W:
        size -= 1
    c.setFont("Helvetica-Bold", size)
    if fill_color is not None:
        c.setFillColor(fill_color)
    elif align == "center":
        c.setFillColor(colors.white)
    if align == "right":
        c.drawRightString(x, y, text)
    else:
        c.drawCentredString(x, y, text)


def _draw_fixed_slot_text(c, x, y, text, font, size):
    c.setFont(font, size)
    c.drawCentredString(x, y, text)


def _draw_wrapped_title(c, x, y, title, max_w):
    c.setFont("Helvetica-Bold", 11)
    words = title.split()
    line = ""
    line_y = y
    for word in words:
        trial = f"{line} {word}".strip()
        if stringWidth(trial, "Helvetica-Bold", 11) <= max_w:
            line = trial
        else:
            if line:
                c.drawString(x, line_y, line)
                line_y -= 0.14 * inch
            line = word
    if line:
        c.drawString(x, line_y, line)


def _draw_arrow_line(c, x1, x2, y):
    if x2 <= x1:
        return
    c.setStrokeColor(DARK_TEXT)
    c.setLineWidth(2)
    pad = 0.06 * inch
    c.line(x1 + pad, y, x2 - pad, y)
    # Arrowhead at end
    ah = 0.1 * inch
    c.line(x2 - pad, y, x2 - pad - ah, y + ah * 0.45)
    c.line(x2 - pad, y, x2 - pad - ah, y - ah * 0.45)
