"""Brewing calculations.

All formulas live here as pure functions. Every function returns None when a
required input is missing or outside the domain of the formula, so callers can
leave the corresponding field empty instead of showing a wrong value.
Results are rounded like the spreadsheet did (half away from zero) and match
the precision of the corresponding database columns where one exists.
"""
import math
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

# Alcohol produced by the priming sugar during secondary fermentation (% vol).
SECONDARY_FERMENTATION_ALCOHOL = Decimal("0.45")
# Grams of sugar per 0.5 l bottle are scaled to 0.33 l by the volume ratio.
BOTTLE_RATIO_033_TO_05 = Decimal(2) / Decimal(3)
BOTTLES_PER_LITER_05 = 2
# Days the bottled beer matures after the maturation start date.
MATURATION_PERIOD_DAYS = 14
KELVIN_OFFSET = 273.15


def _round(value: float, places: int) -> Decimal:
    """Round half away from zero; a result of -0 is returned as 0."""
    exact = Decimal(repr(round(value, 10)))
    rounded = exact.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return rounded + 0 if rounded == 0 else rounded


def _co2_solubility_term(temperature: Decimal) -> float | None:
    """exp(-10.73797 + 2617.25 / (T + 273.15)): CO2 retention at fermentation temperature."""
    kelvin = float(temperature) + KELVIN_OFFSET
    if kelvin <= 0:
        return None
    return math.exp(-10.73797 + 2617.25 / kelvin)


def alcohol_before_secondary_fermentation(
    plato_after_boiling: Decimal | None, plato_current: Decimal | None
) -> Decimal | None:
    """Alcohol (% vol) from original and final gravity in degrees Plato."""
    if plato_after_boiling is None or plato_current is None:
        return None
    original, final = float(plato_after_boiling), float(plato_current)
    denominator = 206.65 - 1.0665 * original
    if denominator <= 0:
        return None
    apparent_extract = 0.1808 * original + 0.8192 * final
    return _round((original - apparent_extract) / denominator * 100 / 0.795, 2)


def alcohol_after_secondary_fermentation(
    alcohol_target: Decimal | None,
) -> Decimal | None:
    """Alcohol (% vol) after secondary fermentation.

    The dilution volume is calculated from the measured values so that the
    target alcohol is reached, hence the result equals the target.
    """
    return alcohol_target


def dilution_volume(
    volume_before: Decimal | None,
    alcohol_target: Decimal | None,
    alcohol_before: Decimal | None,
) -> Decimal | None:
    """Liters of water to add so the beer reaches the target alcohol after priming."""
    if volume_before is None or alcohol_target is None or alcohol_before is None:
        return None
    if alcohol_target <= 0:
        return None
    volume = float(volume_before)
    after_priming = float(alcohol_before + SECONDARY_FERMENTATION_ALCOHOL)
    return _round(volume / float(alcohol_target) * after_priming - volume, 1)


def bottling_volume(
    volume_before: Decimal | None, dilution: Decimal | None
) -> Decimal | None:
    """Liters available for bottling: volume before dilution plus added water."""
    if volume_before is None or dilution is None:
        return None
    return _round(float(volume_before + dilution), 1)


def sugar_per_half_liter_bottle(
    co2_target: Decimal | None, temperature_fermentation: Decimal | None
) -> Decimal | None:
    """Grams of sugar per 0.5 l bottle needed to reach the target CO2 (g/l)."""
    if co2_target is None or temperature_fermentation is None:
        return None
    retained = _co2_solubility_term(temperature_fermentation)
    if retained is None:
        return None
    residual_co2 = 10.13 * retained
    return _round(max(0.0, (float(co2_target) - residual_co2) * 2 * 0.5), 2)


def sugar_per_third_liter_bottle(sugar_half_liter: Decimal | None) -> Decimal | None:
    """Grams of sugar per 0.33 l bottle, derived from the 0.5 l value."""
    if sugar_half_liter is None:
        return None
    return _round(float(sugar_half_liter * BOTTLE_RATIO_033_TO_05), 2)


def sugar_total(
    sugar_half_liter: Decimal | None, bottling_volume_liters: Decimal | None
) -> Decimal | None:
    """Total grams of priming sugar, based on the 0.5 l value and the bottled volume."""
    if sugar_half_liter is None or bottling_volume_liters is None:
        return None
    return _round(float(sugar_half_liter * BOTTLES_PER_LITER_05 * bottling_volume_liters), 0)


def target_pressure(
    co2_target: Decimal | None, temperature_fermentation: Decimal | None
) -> Decimal | None:
    """Target bottle pressure in bar for the target CO2 content (g/l)."""
    if co2_target is None or temperature_fermentation is None:
        return None
    retained = _co2_solubility_term(temperature_fermentation)
    if retained is None:
        return None
    return _round(max(0.0, float(co2_target) / (10 * retained) - 1.013), 1)


def co2_from_pressure(
    pressure_current: Decimal | None, temperature_fermentation: Decimal | None
) -> Decimal | None:
    """CO2 content (g/l) for a measured bottle pressure; inverse of target_pressure."""
    if pressure_current is None or temperature_fermentation is None:
        return None
    retained = _co2_solubility_term(temperature_fermentation)
    if retained is None:
        return None
    return _round((float(pressure_current) + 1.013) * 10 * retained, 1)


STATUS_FERMENTING = "fermenting"
STATUS_MATURING = "maturing"
STATUS_DONE = "done"


def end_date(lagering_startdate: date | None) -> date | None:
    """Date on which the maturation ends; None until the maturation has a start date."""
    if lagering_startdate is None:
        return None
    return lagering_startdate + timedelta(days=MATURATION_PERIOD_DAYS)


def brew_status(lagering_startdate: date | None, today: date) -> str:
    """Fermenting until maturation starts, maturing until its end date, then done."""
    if lagering_startdate is None or lagering_startdate > today:
        return STATUS_FERMENTING
    if today >= lagering_startdate + timedelta(days=MATURATION_PERIOD_DAYS):
        return STATUS_DONE
    return STATUS_MATURING


def _days_between(start: date | None, end: date | None, extra_days: int = 0) -> int | None:
    """Whole days from start to end plus extra_days; None if missing or negative."""
    if start is None or end is None:
        return None
    days = (end - start).days + extra_days
    return days if days >= 0 else None


def main_fermentation_days(
    brewing_date: date | None, bottling_date: date | None
) -> int | None:
    """Days from brewing to bottling."""
    return _days_between(brewing_date, bottling_date)


def maturation_days(
    bottling_date: date | None, lagering_startdate: date | None
) -> int | None:
    """Days between bottling and the start of maturation."""
    return _days_between(bottling_date, lagering_startdate)


def total_days(
    brewing_date: date | None, lagering_startdate: date | None
) -> int | None:
    """Days from brewing until the beer is ready: maturation start plus the maturation period."""
    return _days_between(brewing_date, lagering_startdate, MATURATION_PERIOD_DAYS)
