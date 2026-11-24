"""View models for the brewing log overview and detail pages."""
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy.orm import Session

from app.formatting import EMPTY, de_date, with_unit
from app.models import BrewingLog
from app.repositories import brewing_logs as repo
from app.services import calculations as calc


@dataclass
class OverviewRow:
    brewing_log_id: int
    recipe_name: str
    brewing_date: str
    alcohol: str
    bottling_volume: str
    rating: str


@dataclass
class Row:
    label: str
    value: str
    calculated: bool = False


@dataclass
class Group:
    title: str
    rows: list[Row] = field(default_factory=list)


@dataclass
class Detail:
    log: BrewingLog
    groups: list[Group]


def _rating_of(log: BrewingLog):
    return log.ratings[0] if log.ratings else None


def build_overview(session: Session) -> list[OverviewRow]:
    rows = []
    for log in repo.list_logs(session):
        rating = _rating_of(log)
        rows.append(
            OverviewRow(
                log.brewing_log_id,
                log.recipe.recipe_name,
                de_date(log.brewing_date),
                with_unit(log.alcohol_current, "% vol"),
                with_unit(log.bottling_volume, "l"),
                str(rating.rating) if rating and rating.rating is not None else EMPTY,
            )
        )
    return rows


def _stored_or_calculated(stored: Decimal | None, calculated: Decimal | None) -> tuple[Decimal | None, bool]:
    if stored is not None:
        return stored, False
    return calculated, calculated is not None


def _days(value: int | None) -> str:
    return EMPTY if value is None else f"{value} Tage"


def build_detail(session: Session, brewing_log_id: int) -> Detail | None:
    log = repo.get(session, brewing_log_id)
    if log is None:
        return None
    rating = _rating_of(log)

    alcohol_before, alcohol_before_calc = _stored_or_calculated(
        log.alcohol_before_sec_fermentation,
        calc.alcohol_before_secondary_fermentation(log.plato_after_boiling, log.plato_current),
    )
    dilution_calculated = calc.dilution_volume(
        log.volume_after_fermentation, log.alcohol_target, alcohol_before
    )
    alcohol_after, alcohol_after_calc = _stored_or_calculated(
        log.alcohol_after_sec_fermentation,
        calc.alcohol_after_secondary_fermentation(log.alcohol_target),
    )
    sugar_half = calc.sugar_per_half_liter_bottle(log.co2_target, log.temperature_fermentation)
    sugar_total, sugar_total_calc = _stored_or_calculated(
        log.sugar_total, calc.sugar_total(sugar_half, log.bottling_volume)
    )

    groups = [
        Group("Allgemein", [
            Row("Rezept", log.recipe.recipe_name),
            Row("Braudatum", de_date(log.brewing_date)),
        ]),
        Group("Stammwürze und Brauprozess", [
            Row("Stammwürze Soll", with_unit(log.plato_target, "°P")),
            Row("Stammwürze vor Kochen", with_unit(log.plato_before_boiling, "°P")),
            Row("Wasserzugabe", with_unit(log.water_addition_boiling, "l")),
            Row("Stammwürze nach Kochen", with_unit(log.plato_after_boiling, "°P")),
            Row("Stammwürze bei Abfüllung", with_unit(log.plato_current, "°P")),
        ]),
        Group("Hefe und Abweichungen", [
            Row("Hefe", log.yeast_ingredient.name),
            Row("Gärtemperatur", with_unit(log.temperature_fermentation, "°C")),
            Row("Abweichungen", log.deviations or EMPTY),
        ]),
        Group("Alkohol und Verdünnung", [
            Row("Alkoholgehalt Soll", with_unit(log.alcohol_target, "% vol")),
            Row("Alkoholgehalt vor Nachgärung", with_unit(alcohol_before, "% vol"), alcohol_before_calc),
            Row("Menge vor Verdünnung", with_unit(log.volume_after_fermentation, "l")),
            Row("Verdünnung", with_unit(log.water_addition_fermentation, "l")),
            Row("Verdünnung (berechnet)", with_unit(dilution_calculated, "l"), True),
            Row("Alkoholgehalt nach Nachgärung", with_unit(alcohol_after, "% vol"), alcohol_after_calc),
            Row("Alkoholgehalt aktuell", with_unit(log.alcohol_current, "% vol")),
        ]),
        Group("Geschmack und Karbonisierung", [
            Row("Bewertung (1–10)", str(rating.rating) if rating and rating.rating is not None else EMPTY),
            Row("Geschmack", (rating.remark if rating and rating.remark else EMPTY)),
            Row("Zucker pro 0,5-l-Flasche", with_unit(sugar_half, "g"), True),
            Row("Zucker pro 0,33-l-Flasche", with_unit(calc.sugar_per_third_liter_bottle(sugar_half), "g"), True),
            Row("Zucker gesamt", with_unit(sugar_total, "g"), sugar_total_calc),
            Row("CO₂ Soll", with_unit(log.co2_target, "g/l")),
            Row("CO₂ Ist", with_unit(log.co2_current, "g/l")),
            Row("Zieldruck", with_unit(calc.target_pressure(log.co2_target, log.temperature_fermentation), "bar"), True),
            Row("Druck Ist", with_unit(log.pressure_current, "bar")),
        ]),
        Group("Abfüllung und Reifung", [
            Row("Abfüllmenge", with_unit(log.bottling_volume, "l")),
            Row("Abfülldatum", de_date(log.bottling_date) or EMPTY),
            Row("Reifung Startdatum", de_date(log.lagering_startdate) or EMPTY),
            Row("Dauer Hauptgärung", _days(calc.main_fermentation_days(log.brewing_date, log.bottling_date)), True),
            Row("Dauer Reifung", _days(calc.maturation_days(log.bottling_date, log.lagering_startdate)), True),
            Row("Dauer gesamt", _days(calc.total_days(log.brewing_date, log.lagering_startdate)), True),
        ]),
    ]
    return Detail(log, groups)
