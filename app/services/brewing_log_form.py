"""Validation, derived values and persistence for creating and editing brewing logs."""
import logging
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.formatting import de_decimal, with_unit
from app.models import BrewingLog, Rating, Recipe
from app.parsing import parse_decimal
from app.repositories import brewing_logs as repo
from app.services import calculations as calc

logger = logging.getLogger(__name__)

MAX_RECIPE_NAME_LEN = 255
MAX_DEVIATIONS_LEN = 2000
MAX_REMARK_LEN = 500


@dataclass(frozen=True)
class NumberField:
    """A numeric column; precision and scale are taken from brauprotokoll.sql."""

    name: str
    label: str
    precision: int
    scale: int
    required: bool = False


NUMBER_FIELDS = (
    NumberField("plato_target", "Stammwürze Soll", 3, 1, required=True),
    NumberField("plato_before_boiling", "Stammwürze vor Kochen", 3, 1),
    NumberField("water_addition_boiling", "Wasserzugabe", 2, 1),
    NumberField("plato_after_boiling", "Stammwürze nach Kochen", 3, 1),
    NumberField("plato_current", "Stammwürze bei Abfüllung", 3, 1),
    NumberField("alcohol_target", "Alkoholgehalt Soll", 3, 2, required=True),
    NumberField("alcohol_before_sec_fermentation", "Alkoholgehalt vor Nachgärung", 3, 2),
    NumberField("alcohol_after_sec_fermentation", "Alkoholgehalt nach Nachgärung", 3, 2),
    NumberField("temperature_fermentation", "Gärtemperatur", 3, 1, required=True),
    NumberField("volume_after_fermentation", "Menge vor Verdünnung", 3, 1),
    NumberField("water_addition_fermentation", "Verdünnung", 2, 1),
    NumberField("bottling_volume", "Abfüllmenge", 3, 1),
    NumberField("sugar_total", "Zucker gesamt", 4, 1),
    NumberField("co2_target", "CO₂ Soll", 2, 1, required=True),
    NumberField("pressure_current", "Druck Ist", 3, 2),
)
FIELDS_BY_NAME = {f.name: f for f in NUMBER_FIELDS}
# Not entered by the user: calculated from the measured pressure.
CO2_CURRENT_FIELD = NumberField("co2_current", "CO₂ Ist", 2, 1)
DATE_FIELDS = ("brewing_date", "bottling_date", "lagering_startdate")
TEXT_FIELDS = ("recipe_name", "yeast", "deviations", "rating", "remark")

# Values the user may leave empty to use the calculated value.
AUTOFILL_FIELDS = (
    "alcohol_before_sec_fermentation",
    "water_addition_fermentation",
    "bottling_volume",
    "alcohol_after_sec_fermentation",
    "sugar_total",
)
ZERO_DEFAULT_FIELDS = ("water_addition_boiling", "water_addition_fermentation")

Values = dict[str, "Decimal | date | None"]


def blank_input() -> dict[str, str]:
    return {"brewing_date": date.today().isoformat()}


def input_from_log(log: BrewingLog) -> dict[str, str]:
    raw: dict[str, str] = {
        "recipe_name": log.recipe.recipe_name,
        "yeast": str(log.yeast),
        "deviations": log.deviations or "",
    }
    for field in NUMBER_FIELDS:
        raw[field.name] = de_decimal(getattr(log, field.name))
    for name in DATE_FIELDS:
        value = getattr(log, name)
        raw[name] = value.isoformat() if value else ""
    if log.ratings:
        rating = log.ratings[0]
        raw["rating"] = str(rating.rating) if rating.rating is not None else ""
        raw["remark"] = rating.remark or ""
    return raw


def _parse_date(text: str) -> date | None:
    text = text.strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise ValueError("invalid date")


def check_range(field: NumberField, value: Decimal) -> str | None:
    if value < 0:
        return "Der Wert darf nicht negativ sein."
    if value != value.quantize(Decimal(1).scaleb(-field.scale)):
        digits = "eine Nachkommastelle" if field.scale == 1 else f"{field.scale} Nachkommastellen"
        return f"Höchstens {digits} erlaubt."
    maximum = Decimal(10) ** (field.precision - field.scale) - Decimal(1).scaleb(-field.scale)
    if value > maximum:
        return f"Der Wert darf höchstens {de_decimal(maximum)} betragen."
    return None


def parse(raw: dict[str, str]) -> tuple[Values, dict[str, str]]:
    """Convert the raw form strings into typed values and collect field errors."""
    values: Values = {}
    errors: dict[str, str] = {}
    for field in NUMBER_FIELDS:
        text = raw.get(field.name, "")
        try:
            number = parse_decimal(text)
        except ValueError:
            values[field.name] = None
            errors[field.name] = "Bitte eine Zahl eingeben (z. B. 5,5)."
            continue
        values[field.name] = number
        if number is None:
            if field.required:
                errors[field.name] = "Pflichtfeld."
        elif message := check_range(field, number):
            # An invalid value must not feed the calculations of other fields.
            values[field.name] = None
            errors[field.name] = message
    for name in DATE_FIELDS:
        try:
            values[name] = _parse_date(raw.get(name, ""))
        except ValueError:
            values[name] = None
            errors[name] = "Bitte ein gültiges Datum eingeben."
        else:
            if name == "brewing_date" and values[name] is None:
                errors[name] = "Pflichtfeld."
    return values, errors


@dataclass
class Calculated:
    """Derived values. The *_calc fields hold the pure calculation (for hints);
    the effective fields hold the entered value or, if empty, the calculation."""

    alcohol_before_calc: Decimal | None
    dilution_calc: Decimal | None
    bottling_volume_calc: Decimal | None
    alcohol_after_calc: Decimal | None
    sugar_total_calc: Decimal | None
    effective: dict[str, Decimal | None]
    sugar_half: Decimal | None
    sugar_third: Decimal | None
    target_pressure: Decimal | None
    co2_current: Decimal | None
    main_fermentation_days: int | None
    maturation_days: int | None
    total_days: int | None


def calculate(values: Values) -> Calculated:
    """Chain the calculations; entered values take precedence over calculated ones."""
    v = values
    alcohol_before_calc = calc.alcohol_before_secondary_fermentation(
        v["plato_after_boiling"], v["plato_current"]
    )
    alcohol_before = _first(v["alcohol_before_sec_fermentation"], alcohol_before_calc)

    dilution_calc = calc.dilution_volume(
        v["volume_after_fermentation"], v["alcohol_target"], alcohol_before
    )
    # A negative dilution means the beer is already stronger than the target.
    usable_dilution = dilution_calc if dilution_calc is not None and dilution_calc >= 0 else None
    dilution = _first(v["water_addition_fermentation"], usable_dilution)

    bottling_volume_calc = calc.bottling_volume(
        v["volume_after_fermentation"], dilution if dilution is not None else Decimal(0)
    )
    bottling_volume = _first(v["bottling_volume"], bottling_volume_calc)

    alcohol_after_calc = calc.alcohol_after_secondary_fermentation(v["alcohol_target"])
    sugar_half = calc.sugar_per_half_liter_bottle(v["co2_target"], v["temperature_fermentation"])
    sugar_total_calc = calc.sugar_total(sugar_half, bottling_volume)

    return Calculated(
        alcohol_before_calc=alcohol_before_calc,
        dilution_calc=dilution_calc,
        bottling_volume_calc=bottling_volume_calc,
        alcohol_after_calc=alcohol_after_calc,
        sugar_total_calc=sugar_total_calc,
        effective={
            "alcohol_before_sec_fermentation": alcohol_before,
            "water_addition_fermentation": dilution,
            "bottling_volume": bottling_volume,
            "alcohol_after_sec_fermentation": _first(
                v["alcohol_after_sec_fermentation"], alcohol_after_calc
            ),
            "sugar_total": _first(v["sugar_total"], sugar_total_calc),
        },
        sugar_half=sugar_half,
        sugar_third=calc.sugar_per_third_liter_bottle(sugar_half),
        target_pressure=calc.target_pressure(v["co2_target"], v["temperature_fermentation"]),
        co2_current=calc.co2_from_pressure(v["pressure_current"], v["temperature_fermentation"]),
        main_fermentation_days=calc.main_fermentation_days(v["brewing_date"], v["bottling_date"]),
        maturation_days=calc.maturation_days(v["bottling_date"], v["lagering_startdate"]),
        total_days=calc.total_days(v["brewing_date"], v["lagering_startdate"]),
    )


def _first(entered, calculated):
    return entered if entered is not None else calculated


def live_calculation(raw: dict[str, str]) -> Calculated:
    """Calculation for the live preview; invalid fields are simply treated as empty."""
    values, _ = parse(raw)
    return calculate(values)


def hints(calculated: Calculated) -> dict[str, str]:
    """Hint texts shown next to the fields that can be left empty."""
    pairs = {
        "alcohol_before_sec_fermentation": with_unit(calculated.alcohol_before_calc, "% vol"),
        "water_addition_fermentation": with_unit(calculated.dilution_calc, "l"),
        "bottling_volume": with_unit(calculated.bottling_volume_calc, "l"),
        "alcohol_after_sec_fermentation": with_unit(calculated.alcohol_after_calc, "% vol"),
        "sugar_total": with_unit(calculated.sugar_total_calc, "g"),
    }
    return {name: f"Berechnet: {text}" for name, text in pairs.items() if text != "–"} | {
        name: "" for name, text in pairs.items() if text == "–"
    }


def save(
    session: Session, raw: dict[str, str], brewing_log_id: int | None = None
) -> tuple[BrewingLog | None, dict[str, str]]:
    """Validate and store a brewing log with recipe and rating in one transaction."""
    values, errors = parse(raw)
    calculated = calculate(values)

    # Calculated values replacing empty fields must fit the column as well.
    for name in AUTOFILL_FIELDS:
        if values.get(name) is None and calculated.effective[name] is not None:
            message = check_range(FIELDS_BY_NAME[name], calculated.effective[name])
            if message:
                errors.setdefault(name, f"Der berechnete Wert passt nicht in das Feld, bitte manuell eingeben. ({message})")

    # CO2 Ist is derived from the pressure and has to fit its column as well.
    if calculated.co2_current is not None:
        message = check_range(CO2_CURRENT_FIELD, calculated.co2_current)
        if message:
            errors.setdefault(
                "pressure_current",
                f"Der daraus berechnete CO₂-Wert passt nicht in das Feld. ({message})",
            )

    recipe_name = raw.get("recipe_name", "").strip()
    if not recipe_name:
        errors["recipe_name"] = "Pflichtfeld."
    elif len(recipe_name) > MAX_RECIPE_NAME_LEN:
        errors["recipe_name"] = f"Höchstens {MAX_RECIPE_NAME_LEN} Zeichen erlaubt."

    deviations = raw.get("deviations", "").strip()
    if len(deviations) > MAX_DEVIATIONS_LEN:
        errors["deviations"] = f"Höchstens {MAX_DEVIATIONS_LEN} Zeichen erlaubt."
    remark = raw.get("remark", "").strip()
    if len(remark) > MAX_REMARK_LEN:
        errors["remark"] = f"Höchstens {MAX_REMARK_LEN} Zeichen erlaubt."

    rating_value: int | None = None
    rating_text = raw.get("rating", "").strip()
    if rating_text:
        try:
            rating_value = int(rating_text)
        except ValueError:
            errors["rating"] = "Bitte eine ganze Zahl von 1 bis 10 eingeben."
        else:
            if not 1 <= rating_value <= 10:
                errors["rating"] = "Die Bewertung muss zwischen 1 und 10 liegen."

    yeast = None
    try:
        yeast = repo.get_ingredient(session, int(raw.get("yeast", "")))
    except ValueError:
        pass
    if yeast is None or yeast.ingredient_type != repo.YEAST_TYPE:
        errors["yeast"] = "Bitte eine Hefe auswählen."

    log = None
    if brewing_log_id is not None:
        log = repo.get(session, brewing_log_id)
        if log is None:
            errors["_general"] = "Der Sud existiert nicht mehr."

    if errors:
        return None, errors

    try:
        recipe = repo.find_recipe(session, recipe_name) or Recipe(recipe_name=recipe_name)
        if log is None:
            log = BrewingLog()
            session.add(log)
        log.recipe = recipe
        log.yeast_ingredient = yeast
        log.deviations = deviations or None
        for field in NUMBER_FIELDS:
            value = calculated.effective.get(field.name, values[field.name])
            if value is None and field.name in ZERO_DEFAULT_FIELDS:
                value = Decimal(0)
            setattr(log, field.name, value)
        log.co2_current = calculated.co2_current
        for name in DATE_FIELDS:
            setattr(log, name, values[name])
        _apply_rating(log, rating_value, remark)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Saving brewing log failed")
        return None, {"_general": "Speichern fehlgeschlagen. Es wurde nichts geändert."}
    return log, {}


def _apply_rating(log: BrewingLog, rating_value: int | None, remark: str) -> None:
    if rating_value is None and not remark:
        log.ratings = []
    elif log.ratings:
        log.ratings[0].rating = rating_value
        log.ratings[0].remark = remark or None
    else:
        log.ratings = [Rating(rating=rating_value, remark=remark or None)]


def delete(session: Session, brewing_log_id: int) -> str | None:
    """Delete a brewing log with its rating; returns an error message or None."""
    log = repo.get(session, brewing_log_id)
    if log is None:
        return "Der Sud existiert nicht mehr."
    try:
        session.delete(log)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Deleting brewing log failed")
        return "Löschen fehlgeschlagen. Es wurde nichts geändert."
    return None
