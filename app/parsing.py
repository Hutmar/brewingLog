"""Parsing of user input independent of the browser locale."""
from decimal import Decimal, InvalidOperation


def parse_decimal(text: str | None) -> Decimal | None:
    """Parse a decimal number written with either ',' or '.' as separator.

    Returns None for empty input and raises ValueError for anything that is
    not a plain number (including values using both separators, which would
    be ambiguous).
    """
    if text is None:
        return None
    cleaned = text.strip().replace(" ", "")
    if not cleaned:
        return None
    if "," in cleaned and "." in cleaned:
        raise ValueError("ambiguous decimal separators")
    try:
        value = Decimal(cleaned.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError("not a number") from exc
    if not value.is_finite():
        raise ValueError("not a finite number")
    return value
