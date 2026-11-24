"""Display formatting for numbers and dates (German conventions)."""
from datetime import date
from decimal import Decimal

EMPTY = "–"


def de_decimal(value: Decimal | float | int | None) -> str:
    """Format a number with a decimal comma; None becomes an empty string."""
    if value is None:
        return ""
    return str(value).replace(".", ",")


def de_date(value: date | None) -> str:
    return value.strftime("%d.%m.%Y") if value else ""


def with_unit(value: Decimal | int | None, unit: str = "") -> str:
    """Number with unit for read-only views; a dash marks a missing value."""
    if value is None:
        return EMPTY
    text = de_decimal(value)
    return f"{text} {unit}" if unit else text
