"""View models for the brewing log overview and detail pages."""
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from urllib.parse import quote, unquote

from sqlalchemy.orm import Session

from app.formatting import EMPTY, de_date, with_unit
from app.models import BrewingLog
from app.repositories import brewing_logs as repo
from app.services import calculations as calc

SORT_STATUS, SORT_DATE, SORT_RECIPE = "status", "date", "recipe"
SORT_KEYS = (SORT_STATUS, SORT_DATE, SORT_RECIPE)
ASC, DESC = "asc", "desc"
MAX_SEARCH_LEN = 100

STATUS_LABELS = {
    calc.STATUS_FERMENTING: "In Gärung",
    calc.STATUS_MATURING: "In Reifung",
    calc.STATUS_DONE: "Abgeschlossen",
}
_STATUS_ORDER = {calc.STATUS_FERMENTING: 0, calc.STATUS_MATURING: 1, calc.STATUS_DONE: 2}


@dataclass(frozen=True)
class ViewPrefs:
    """Search text and sort order of the overview; kept between requests."""

    q: str = ""
    sort: str = SORT_DATE
    direction: str = DESC

    @classmethod
    def build(cls, q: str | None, sort: str | None, direction: str | None, base: "ViewPrefs") -> "ViewPrefs":
        """Overlay the given values on base; invalid values keep the base value."""
        return cls(
            q=base.q if q is None else q.strip()[:MAX_SEARCH_LEN],
            sort=sort if sort in SORT_KEYS else base.sort,
            direction=direction if direction in (ASC, DESC) else base.direction,
        )

    def to_cookie(self) -> str:
        return quote(json.dumps({"q": self.q, "sort": self.sort, "dir": self.direction}))

    @classmethod
    def from_cookie(cls, value: str | None) -> "ViewPrefs":
        """Read the cookie written by to_cookie; anything unreadable yields the defaults."""
        if not value:
            return cls()
        try:
            data = json.loads(unquote(value))
            return cls.build(str(data.get("q", "")), data.get("sort"), data.get("dir"), cls())
        except (ValueError, AttributeError):
            return cls()


@dataclass
class OverviewRow:
    brewing_log_id: int
    recipe_name: str
    brewing_date: str
    end_date: str
    status: str
    status_label: str
    alcohol: str
    bottling_volume: str
    rating: str


@dataclass
class Column:
    key: str
    label: str
    next_direction: str
    indicator: str


@dataclass
class Overview:
    prefs: ViewPrefs
    columns: dict[str, Column]
    rows: list[OverviewRow]


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


def _sort_key(log: BrewingLog, status: str, sort: str):
    if sort == SORT_STATUS:
        return (_STATUS_ORDER[status], log.brewing_date)
    if sort == SORT_RECIPE:
        return (log.recipe.recipe_name.casefold(), log.brewing_date)
    return (log.brewing_date, log.brewing_log_id)


def _columns(prefs: ViewPrefs) -> dict[str, Column]:
    labels = {SORT_STATUS: "Status", SORT_DATE: "Braudatum", SORT_RECIPE: "Rezept"}
    columns = {}
    for key, label in labels.items():
        active = prefs.sort == key
        next_direction = (ASC if prefs.direction == DESC else DESC) if active else ASC
        indicator = ("▲" if prefs.direction == ASC else "▼") if active else ""
        columns[key] = Column(key, label, next_direction, indicator)
    return columns


def build_overview(session: Session, prefs: ViewPrefs, today: date | None = None) -> Overview:
    today = today or date.today()
    entries = []
    for log in repo.list_logs(session, prefs.q):
        status = calc.brew_status(log.lagering_startdate, today)
        rating = _rating_of(log)
        row = OverviewRow(
            log.brewing_log_id,
            log.recipe.recipe_name,
            de_date(log.brewing_date),
            de_date(calc.end_date(log.lagering_startdate)) or EMPTY,
            status,
            STATUS_LABELS[status],
            with_unit(log.alcohol_after_sec_fermentation, "% vol"),
            with_unit(log.bottling_volume, "l"),
            str(rating.rating) if rating and rating.rating is not None else EMPTY,
        )
        entries.append((_sort_key(log, status, prefs.sort), row))
    entries.sort(key=lambda entry: entry[0], reverse=prefs.direction == DESC)
    return Overview(prefs, _columns(prefs), [row for _, row in entries])


def _stored_or_calculated(stored: Decimal | None, calculated: Decimal | None) -> tuple[Decimal | None, bool]:
    if stored is not None:
        return stored, False
    return calculated, calculated is not None


def _days(value: int | None) -> str:
    return EMPTY if value is None else f"{value} Tage"


def build_detail(session: Session, brewing_log_id: int, today: date | None = None) -> Detail | None:
    log = repo.get(session, brewing_log_id)
    if log is None:
        return None
    today = today or date.today()
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
    co2_current, co2_current_calc = _stored_or_calculated(
        log.co2_current, calc.co2_from_pressure(log.pressure_current, log.temperature_fermentation)
    )
    end = calc.end_date(log.lagering_startdate)
    status = calc.brew_status(log.lagering_startdate, today)

    groups = [
        Group("Allgemein", [
            Row("Rezept", log.recipe.recipe_name),
            Row("Braudatum", de_date(log.brewing_date)),
            Row("Enddatum", de_date(end) or EMPTY, end is not None),
            Row("Status", STATUS_LABELS[status]),
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
        ]),
        Group("Karbonisierung", [
            Row("Zucker pro 0,5-l-Flasche", with_unit(sugar_half, "g"), True),
            Row("Zucker pro 0,33-l-Flasche", with_unit(calc.sugar_per_third_liter_bottle(sugar_half), "g"), True),
            Row("Zucker gesamt", with_unit(sugar_total, "g"), sugar_total_calc),
            Row("CO₂ Soll", with_unit(log.co2_target, "g/l")),
            Row("CO₂ Ist", with_unit(co2_current, "g/l"), co2_current_calc),
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
        Group("Bewertung", [
            Row("Bewertung (1–10)", str(rating.rating) if rating and rating.rating is not None else EMPTY),
            Row("Geschmack", (rating.remark if rating and rating.remark else EMPTY)),
        ]),
    ]
    return Detail(log, groups)
