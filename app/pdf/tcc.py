from __future__ import annotations

import math
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.database import age_from_dob
from app.pdf.utils import BRAND_BLUE, DARK_TEXT, GRAY_BOX, GREEN, MARGIN, money

HEADER_H = 1.0 * inch
HEADER_CONTENT_GAP = 0.32 * inch  # space between blue header and green client cards
SUMMARY_BAR_H = 0.85 * inch
SECTION_GAP = 0.32 * inch
PAD_X = 0.14 * inch
PAD_Y = 0.1 * inch
TITLE_LEAD = 0.22 * inch
BUBBLE_TO_TOTAL_GAP = 0.06 * inch
TOTAL_BOX_H = 0.58 * inch
MIN_BOX_W = 1.4 * inch
MAX_BUBBLE_R = 0.5 * inch
MIN_BUBBLE_R = 0.32 * inch
BUBBLE_GAP = 0.18 * inch


def generate_tcc_pdf(payload: dict) -> bytes:
    client = payload["client"]
    report = payload["report"]
    calc = payload["report"]["calculations"]
    tcc = calc["tcc"]
    persons = {p["role"]: p for p in payload["persons"]}
    accounts = calc["accounts"]
    is_married = bool(client.get("is_married"))

    c1 = [a for a in accounts if a["category"] == "retirement_c1"]
    c2 = [a for a in accounts if a["category"] == "retirement_c2"]
    non_ret = [a for a in accounts if a["category"] == "non_retirement"]
    trust = [a for a in accounts if a["category"] == "trust"]
    liabilities = [a for a in accounts if a["category"] == "liability"]

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    content_left = MARGIN
    content_right = width - MARGIN
    content_w = content_right - content_left
    col_gap = 0.2 * inch
    col_w = (content_w - col_gap) / 2 if is_married else content_w

    scale = _compute_scale(height, is_married, c1, c2, non_ret, trust, liabilities, content_w, col_w)
    trust_r = 0.55 * inch * scale
    gap = BUBBLE_GAP * scale

    # Dynamic bubble sizing per section so 2 or 5+ bubbles all fit nicely
    retirement_max = max(len(c1), len(c2)) if is_married else len(c1)
    retirement_r = _fit_bubble_radius(retirement_max, col_w, gap, scale)
    non_ret_box_w = _summary_box_width("Non-Retirement Total", tcc["non_retirement_total"])
    non_ret_avail = content_w - non_ret_box_w - 0.22 * inch
    non_ret_r = _fit_bubble_radius(len(non_ret), non_ret_avail, gap, scale)

    _draw_header(c, width, height, client, report)

    # Cursor = top edge (high Y) of next section; moves downward (decreasing Y) after each block
    y = height - HEADER_H - HEADER_CONTENT_GAP * scale
    y = _draw_person_cards(c, content_left, y, persons, is_married, col_w, col_gap, scale)
    y -= SECTION_GAP * scale

    if is_married:
        b1 = _draw_retirement_column(
            c, content_left, y, col_w,
            "Client 1 — Retirement", c1, tcc["client1_retirement_total"],
            "Client 1 Retirement Total", retirement_r, gap,
        )
        b2 = _draw_retirement_column(
            c, content_left + col_w + col_gap, y, col_w,
            "Client 2 — Retirement", c2, tcc["client2_retirement_total"],
            "Client 2 Retirement Total", retirement_r, gap,
        )
        y = min(b1, b2)
    else:
        y = _draw_retirement_column(
            c, content_left, y, content_w,
            "Client 1 — Retirement", c1, tcc["client1_retirement_total"],
            "Client 1 Retirement Total", retirement_r, gap,
        )

    y -= SECTION_GAP * scale

    if trust:
        y = _draw_trust_zone(c, width, y, trust[0], trust_r)
        y -= SECTION_GAP * scale

    y = _draw_non_retirement_section(
        c, content_left, content_right, content_w, y,
        non_ret, tcc["non_retirement_total"], non_ret_r, gap,
    )
    y -= SECTION_GAP * scale

    if liabilities:
        y = _draw_liabilities_zone(
            c, content_left, content_right, y, liabilities, tcc["liabilities_total"]
        )

    _draw_grand_summary_bar(c, width, tcc, is_married)

    c.save()
    buffer.seek(0)
    return buffer.read()


def _fit_bubble_radius(n: int, max_w: float, gap: float, scale: float) -> float:
    """Largest radius that fits N bubbles in one row of max_w; clamped to [MIN, MAX]."""
    max_r = MAX_BUBBLE_R * scale
    min_r = MIN_BUBBLE_R * scale
    if n <= 0:
        return max_r
    r_fit = (max_w - max(0, n - 1) * gap) / (2 * n)
    return max(min_r, min(max_r, r_fit))


def _compute_scale(page_h, is_married, c1, c2, non_ret, trust, liabilities, content_w, col_w) -> float:
    footer = SUMMARY_BAR_H + 0.15 * inch
    available = page_h - HEADER_H - footer - 0.5 * inch
    est = 0.65 * inch + HEADER_CONTENT_GAP  # persons + header gap
    est += _column_height_est(max(len(c1), len(c2) if is_married else len(c1)), col_w if is_married else content_w)
    if trust:
        est += 1.15 * inch
    est += _column_height_est(len(non_ret), content_w)
    if liabilities:
        est += 0.35 + len(liabilities) * 0.5 * inch
    if est <= available:
        return 1.0
    return max(0.65, min(1.0, available / est))


def _column_height_est(n: int, max_w: float) -> float:
    r, g = 0.46 * inch, 0.24 * inch
    rows = _row_count(n, max_w, r, g) if n else 0
    bubble_h = rows * (2 * r + 0.14 * inch) if rows else 0
    return TITLE_LEAD + bubble_h + TOTAL_BOX_H + 0.12 * inch


def _row_count(n: int, max_w: float, bubble_r: float, gap: float) -> int:
    if n == 0:
        return 0
    step = 2 * bubble_r + gap
    per_row = max(1, int((max_w + gap) // step))
    return math.ceil(n / per_row)


def _draw_header(c, width, height, client, report):
    c.setFillColor(BRAND_BLUE)
    c.rect(0, height - HEADER_H, width, HEADER_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(MARGIN, height - 0.58 * inch, "Total Client Chart (TCC)")
    c.setFont("Helvetica", 11)
    c.drawString(MARGIN, height - 0.82 * inch, client["display_name"])
    c.drawRightString(width - MARGIN, height - 0.82 * inch, report["quarter_label"])


def _draw_person_cards(c, x, y, persons, is_married, col_w, col_gap, scale) -> float:
    """Return Y below person cards (cursor for next section)."""
    roles = ["client1", "client2"] if is_married else ["client1"]
    card_h = (0.48 * inch + 2 * PAD_Y) * scale
    for i, role in enumerate(roles):
        person = persons.get(role)
        if not person:
            continue
        card_w = _text_width(person) * scale
        bx = x + i * (col_w + col_gap) if is_married else x
        c.setFillColor(GREEN)
        c.roundRect(bx, y - card_h, card_w, card_h, 10, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(bx + PAD_X, y - 0.22 * inch * scale, person["full_name"])
        c.setFont("Helvetica", 7.5)
        age = age_from_dob(person["date_of_birth"])
        c.drawString(
            bx + PAD_X, y - 0.4 * inch * scale,
            f"Age {age} · DOB {person['date_of_birth']} · SSN …{person['ssn_last_four']}",
        )
    return y - card_h


def _text_width(person) -> float:
    name = person["full_name"]
    age = age_from_dob(person["date_of_birth"])
    detail = f"Age {age} · DOB {person['date_of_birth']} · SSN …{person['ssn_last_four']}"
    return max(stringWidth(name, "Helvetica-Bold", 10), stringWidth(detail, "Helvetica", 7.5)) + 2 * PAD_X


def _draw_retirement_column(
    c, x, zone_top, col_w, title, accounts, total, total_label, bubble_r, gap
) -> float:
    """Bubbles in a horizontal row; total box centered underneath."""
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x, zone_top, title)

    bubble_top = zone_top - TITLE_LEAD
    min_bottom = _draw_bubbles_horizontal(c, x, bubble_top, col_w, accounts, bubble_r, gap)

    box_w = _summary_box_width(total_label, total)
    # min_bottom is already the bottom edge of the lowest circle (Y↑ in ReportLab)
    total_center_y = min_bottom - BUBBLE_TO_TOTAL_GAP - TOTAL_BOX_H / 2
    box_x = x + (col_w - box_w) / 2
    _draw_summary_box(c, box_x, total_center_y, total_label, total, box_w)
    return total_center_y - TOTAL_BOX_H / 2


def _draw_bubbles_horizontal(c, x, bubble_top, max_w, accounts, bubble_r, gap) -> float:
    """Place circles side-by-side; wrap to next row only when column is too narrow."""
    if not accounts:
        return bubble_top - bubble_r

    n = len(accounts)
    row_gap = gap
    needed = n * (2 * bubble_r) + (n - 1) * row_gap
    if needed > max_w and n > 1:
        row_gap = max(0.06 * inch, (max_w - n * 2 * bubble_r) / (n - 1))

    row_y = bubble_top - bubble_r
    x_cursor = x + bubble_r
    row_start = x
    min_bottom = row_y - bubble_r
    step = 2 * bubble_r + row_gap

    for i, acc in enumerate(accounts):
        if x_cursor + bubble_r > row_start + max_w and i > 0:
            row_y -= 2 * bubble_r + 0.08 * inch
            x_cursor = row_start + bubble_r
        min_bottom = min(min_bottom, row_y - bubble_r)
        _draw_account_bubble(c, x_cursor, row_y, acc, bubble_r)
        x_cursor += step

    return min_bottom


def _draw_non_retirement_section(
    c, x_left, x_right, max_w, zone_top, accounts, total, bubble_r, gap
) -> float:
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x_left, zone_top, "Non-Retirement Accounts")

    bubble_top = zone_top - TITLE_LEAD
    box_w = _summary_box_width("Non-Retirement Total", total)
    strip_gap = 0.22 * inch
    bubble_area_w = max_w - box_w - strip_gap

    # Place total beside bubbles when there is room on the same row band
    horizontal = bool(accounts) and bubble_area_w >= 2 * bubble_r + gap

    if horizontal:
        min_bottom = _draw_bubbles_horizontal(
            c, x_left, bubble_top, bubble_area_w, accounts, bubble_r, gap
        )
        # Circle centers at bubble_top - r; circle tops at bubble_top (ReportLab Y↑)
        circle_top_y = bubble_top
        box_top_y = circle_top_y
        total_center_y = box_top_y - TOTAL_BOX_H / 2
        _draw_summary_box(
            c, x_right - box_w, total_center_y, "Non-Retirement Total", total, box_w
        )
        row_bottom = min(min_bottom, box_top_y - TOTAL_BOX_H)
        return row_bottom

    min_bottom = _draw_bubble_grid(c, x_left, bubble_top, max_w, accounts, bubble_r, gap)
    total_center_y = min_bottom - 0.1 * inch - TOTAL_BOX_H / 2
    _draw_summary_box(c, x_right - box_w, total_center_y, "Non-Retirement Total", total, box_w)
    return total_center_y - TOTAL_BOX_H / 2


def _draw_bubble_grid(c, x, bubble_top, max_w, accounts, bubble_r, gap) -> float:
    if not accounts:
        return bubble_top - bubble_r

    row_y = bubble_top - bubble_r
    x_cursor = x + bubble_r
    row_start = x
    min_bottom = row_y - bubble_r

    for acc in accounts:
        step = 2 * bubble_r + gap
        if x_cursor + bubble_r > row_start + max_w and x_cursor > row_start + bubble_r:
            row_y -= 2 * bubble_r + 0.08 * inch
            x_cursor = row_start + bubble_r
        min_bottom = min(min_bottom, row_y - bubble_r)
        _draw_account_bubble(c, x_cursor, row_y, acc, bubble_r)
        x_cursor += step

    return min_bottom


def _draw_trust_zone(c, width, zone_top, account, trust_r) -> float:
    """Trust centered; equal padding above and below the circle."""
    trust_title_depth = 0.13 * inch
    circle_pad = 0.14 * inch

    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawCentredString(width / 2, zone_top, "Trust / Residence")

    circle_top = zone_top - trust_title_depth - circle_pad
    cy = circle_top - trust_r
    _draw_account_bubble(c, width / 2, cy, account, trust_r, highlight=True)

    text_y = circle_top - 2 * trust_r - circle_pad
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica", 7.5)
    c.drawCentredString(width / 2, text_y, "Zillow Value")
    text_y -= 0.12 * inch

    addr = (account.get("property_address") or "").strip()
    if addr:
        if len(addr) > 44:
            mid = addr.rfind(" ", 0, len(addr) // 2 + 8)
            if mid < 8:
                mid = len(addr) // 2
            c.drawCentredString(width / 2, text_y, addr[:mid].strip())
            text_y -= 0.11 * inch
            c.drawCentredString(width / 2, text_y, addr[mid:].strip())
            text_y -= 0.09 * inch
        else:
            c.drawCentredString(width / 2, text_y, addr)
            text_y -= 0.09 * inch

    return text_y


def _draw_account_bubble(c, cx, cy, account, radius, highlight=False):
    fill = BRAND_BLUE if highlight else colors.HexColor("#5c6bc0")
    c.setFillColor(fill)
    c.circle(cx, cy, radius, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8)
    c.drawCentredString(cx, cy + radius * 0.38, account.get("account_type", ""))
    c.setFont("Helvetica", 7)
    last4 = account.get("account_last_four") or "—"
    c.drawCentredString(cx, cy + radius * 0.1, f"…{last4}")
    c.setFont("Helvetica-Bold", 9)
    c.drawCentredString(cx, cy - radius * 0.2, money(account.get("balance", 0)))
    cash = account.get("cash_balance") or 0
    if cash and account.get("category") in ("non_retirement", "retirement_c1", "retirement_c2"):
        c.setFont("Helvetica", 6)
        c.drawCentredString(cx, cy - radius * 0.4, f"Cash: {money(cash)}")


def _summary_box_width(label: str, total) -> float:
    lw = stringWidth(label, "Helvetica", 7)
    vw = stringWidth(money(total), "Helvetica-Bold", 11)
    return max(MIN_BOX_W, lw + 0.15 * inch, vw + 0.2 * inch)


def _draw_summary_box(c, box_x, center_y, label, total, box_w: float | None = None):
    if box_w is None:
        box_w = _summary_box_width(label, total)
    box_y = center_y - TOTAL_BOX_H / 2
    c.setFillColor(GRAY_BOX)
    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(1)
    c.roundRect(box_x, box_y, box_w, TOTAL_BOX_H, 6, fill=1, stroke=1)
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica", 7)
    c.drawString(box_x + 0.08 * inch, box_y + TOTAL_BOX_H - 0.18 * inch, label)
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(box_x + box_w - 0.08 * inch, box_y + 0.1 * inch, money(total))


def _draw_liabilities_zone(c, x_left, x_right, zone_top, liabilities, total) -> float:
    c.setFillColor(DARK_TEXT)
    c.setFont("Helvetica-Bold", 9.5)
    c.drawString(x_left, zone_top, "Liabilities (not included in net worth)")

    y = zone_top - TITLE_LEAD
    row_h = 0.44 * inch
    for item in liabilities:
        row_w = _liability_row_width(item)
        c.setFillColor(colors.HexColor("#ffebee"))
        c.setStrokeColor(colors.HexColor("#c62828"))
        c.setLineWidth(1)
        c.roundRect(x_left, y - row_h, row_w, row_h - 0.04 * inch, 5, fill=1, stroke=1)
        c.setFillColor(DARK_TEXT)
        c.setFont("Helvetica-Bold", 8.5)
        c.drawString(x_left + 0.1 * inch, y - 0.18 * inch, item.get("label", item.get("account_type", "")))
        rate = item.get("interest_rate")
        rate_txt = f" @ {rate}%" if rate is not None else ""
        c.setFont("Helvetica", 7.5)
        c.drawString(x_left + 0.1 * inch, y - 0.32 * inch, f"{item.get('account_type', '')}{rate_txt}")
        c.setFont("Helvetica-Bold", 9.5)
        c.drawRightString(x_left + row_w - 0.1 * inch, y - 0.25 * inch, money(item.get("balance", 0)))
        y -= row_h + 0.05 * inch

    box_w = _summary_box_width("Liabilities Total", total)
    mid_y = (zone_top - TITLE_LEAD + y) / 2
    _draw_summary_box(c, x_right - box_w, mid_y, "Liabilities Total", total, box_w)
    return y


def _liability_row_width(item) -> float:
    label = item.get("label") or item.get("account_type", "Liability")
    rate = item.get("interest_rate")
    rate_txt = f" @ {rate}%" if rate is not None else ""
    sub = f"{item.get('account_type', '')}{rate_txt}"
    bal = money(item.get("balance", 0))
    left_w = max(stringWidth(label, "Helvetica-Bold", 8.5), stringWidth(sub, "Helvetica", 7.5))
    return left_w + stringWidth(bal, "Helvetica-Bold", 9.5) + 0.4 * inch


def _draw_grand_summary_bar(c, width, tcc, is_married):
    c.setFillColor(BRAND_BLUE)
    c.rect(0, 0, width, SUMMARY_BAR_H, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 8.5)
    items = [("C1 Retirement", tcc["client1_retirement_total"])]
    if is_married:
        items.append(("C2 Retirement", tcc["client2_retirement_total"]))
    items.extend([
        ("Non-Retirement", tcc["non_retirement_total"]),
        ("Trust", tcc["trust_value"]),
        ("Grand Total", tcc["grand_total"]),
    ])
    slot = (width - 2 * MARGIN) / len(items)
    for i, (label, val) in enumerate(items):
        x = MARGIN + i * slot
        c.drawString(x, 0.47 * inch, label)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, 0.17 * inch, money(val))
        c.setFont("Helvetica-Bold", 8.5)
