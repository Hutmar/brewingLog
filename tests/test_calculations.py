"""Reference values are taken from the formulas and results of the former spreadsheet."""
from datetime import date
from decimal import Decimal as D

import pytest

from app.services import calculations as calc


@pytest.mark.parametrize(
    ("after_boiling", "current", "expected"),
    [("13.6", "3", "5.68"), ("12.5", "2.5", "5.33")],
)
def test_alcohol_before_secondary(after_boiling, current, expected):
    assert calc.alcohol_before_secondary_fermentation(D(after_boiling), D(current)) == D(expected)


@pytest.mark.parametrize(
    ("volume", "target", "before", "expected"),
    [("19", "5.7", "5.68", "1.4"), ("19", "5.5", "5.33", "1.0"), ("20.5", "5.65", "5.34", "0.5")],
)
def test_dilution_volume(volume, target, before, expected):
    assert calc.dilution_volume(D(volume), D(target), D(before)) == D(expected)


def test_dilution_never_returns_negative_zero():
    # 20 / 5.58 * (5.12 + 0.45) - 20 is slightly negative and rounds to -0.0.
    result = calc.dilution_volume(D("20"), D("5.58"), D("5.12"))
    assert result == 0
    assert str(result) == "0.0"


def test_alcohol_after_secondary_equals_target():
    assert calc.alcohol_after_secondary_fermentation(D("5.7")) == D("5.7")
    assert calc.alcohol_after_secondary_fermentation(None) is None


def test_bottling_volume():
    assert calc.bottling_volume(D("19"), D("1.4")) == D("20.4")


@pytest.mark.parametrize(
    ("co2", "temperature", "expected"),
    [("5.4", "13", "3.34"), ("5.6", "13", "3.54")],
)
def test_sugar_per_half_liter_bottle(co2, temperature, expected):
    assert calc.sugar_per_half_liter_bottle(D(co2), D(temperature)) == D(expected)


def test_sugar_never_negative():
    assert calc.sugar_per_half_liter_bottle(D("1"), D("20")) == D("0.00")


def test_sugar_per_third_liter_bottle():
    assert calc.sugar_per_third_liter_bottle(D("3.6")) == D("2.40")


@pytest.mark.parametrize(
    ("sugar", "volume", "expected"),
    [("3.34", "20.4", "136"), ("3.54", "20", "142")],
)
def test_sugar_total(sugar, volume, expected):
    assert calc.sugar_total(D(sugar), D(volume)) == D(expected)


@pytest.mark.parametrize(
    ("co2", "temperature", "expected"),
    [("5.4", "13", "1.6"), ("5.6", "13", "1.7")],
)
def test_target_pressure(co2, temperature, expected):
    assert calc.target_pressure(D(co2), D(temperature)) == D(expected)


def test_maturation_days():
    assert calc.maturation_days(date(2026, 11, 1), date(2026, 11, 11)) == 10
    assert calc.maturation_days(date(2026, 11, 11), date(2026, 11, 1)) is None
    assert calc.maturation_days(None, date(2026, 11, 1)) is None


def test_main_fermentation_and_total_days():
    # Total = 22 days until maturation start + 14 days maturation period.
    brewing, bottling, lagering = date(2026, 3, 1), date(2026, 3, 13), date(2026, 3, 23)
    assert calc.main_fermentation_days(brewing, bottling) == 12
    assert calc.total_days(brewing, lagering) == 36
    assert calc.main_fermentation_days(bottling, brewing) is None
    assert calc.total_days(None, lagering) is None


def test_missing_inputs_yield_none():
    assert calc.alcohol_before_secondary_fermentation(None, D("3")) is None
    assert calc.dilution_volume(D("19"), None, D("5")) is None
    assert calc.dilution_volume(D("19"), D("0"), D("5")) is None
    assert calc.sugar_per_half_liter_bottle(D("5.4"), None) is None
    assert calc.sugar_per_half_liter_bottle(D("5.4"), D("-300")) is None
    assert calc.target_pressure(None, D("13")) is None
    assert calc.sugar_total(None, D("20")) is None


@pytest.mark.parametrize(
    ("pressure", "temperature", "expected"),
    [("1.6", "13", "5.3"), ("2.3", "20", "5.4"), ("0", "13", "2.1")],
)
def test_co2_from_pressure(pressure, temperature, expected):
    assert calc.co2_from_pressure(D(pressure), D(temperature)) == D(expected)


def test_co2_from_pressure_inverts_target_pressure():
    for co2 in ("4.8", "5.4", "6.0"):
        pressure = calc.target_pressure(D(co2), D("13"))
        assert abs(calc.co2_from_pressure(pressure, D("13")) - D(co2)) <= D("0.2")


def test_co2_from_pressure_missing_inputs():
    assert calc.co2_from_pressure(None, D("13")) is None
    assert calc.co2_from_pressure(D("1.6"), None) is None
    assert calc.co2_from_pressure(D("1.6"), D("-300")) is None


def test_end_date_is_maturation_start_plus_period():
    assert calc.end_date(date(2026, 3, 23)) == date(2026, 4, 6)
    assert calc.end_date(None) is None


@pytest.mark.parametrize(
    ("start", "today", "expected"),
    [
        (None, date(2026, 4, 15), "fermenting"),
        (date(2026, 4, 20), date(2026, 4, 15), "fermenting"),  # maturation not started yet
        (date(2026, 4, 15), date(2026, 4, 15), "maturing"),
        (date(2026, 4, 2), date(2026, 4, 15), "maturing"),  # 13 days
        (date(2026, 4, 1), date(2026, 4, 15), "done"),  # exactly 14 days
        (date(2026, 1, 1), date(2026, 4, 15), "done"),
    ],
)
def test_brew_status(start, today, expected):
    assert calc.brew_status(start, today) == expected
