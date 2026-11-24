from decimal import Decimal

import pytest

from app.parsing import parse_decimal


@pytest.mark.parametrize(
    ("text", "expected"),
    [("1,5", Decimal("1.5")), ("1.5", Decimal("1.5")), (" 12 ", Decimal("12")), ("-0,25", Decimal("-0.25"))],
)
def test_parse_decimal_accepts_comma_and_dot(text, expected):
    assert parse_decimal(text) == expected


@pytest.mark.parametrize("text", [None, "", "   "])
def test_parse_decimal_empty_is_none(text):
    assert parse_decimal(text) is None


@pytest.mark.parametrize("text", ["abc", "1,234.5", "NaN", "Infinity", "1,2,3"])
def test_parse_decimal_rejects_invalid(text):
    with pytest.raises(ValueError):
        parse_decimal(text)
