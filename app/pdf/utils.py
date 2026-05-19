from reportlab.lib import colors
from reportlab.lib.units import inch

BRAND_BLUE = colors.HexColor("#1e4d8c")
BRAND_LIGHT_BLUE = colors.HexColor("#e8f1fa")
GREEN = colors.HexColor("#2e7d32")
RED = colors.HexColor("#c62828")
GRAY_BOX = colors.HexColor("#eceff1")
DARK_TEXT = colors.HexColor("#1a1a2e")


def money(value: float) -> str:
    return f"${value:,.0f}"


def money_decimal(value: float) -> str:
    return f"${value:,.2f}"


PAGE_WIDTH = 8.5 * inch
PAGE_HEIGHT = 11 * inch
MARGIN = 0.6 * inch
