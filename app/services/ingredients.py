"""Business logic for the ingredient management."""
import logging
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Ingredient, IngredientAttribute
from app.parsing import parse_decimal
from app.repositories import ingredients as repo

logger = logging.getLogger(__name__)

DEFAULT_TYPES = ("Malz", "Hopfen", "Hefe")
DEFAULT_UNITS = ("kg", "g", "pkg")
DEFAULT_UNIT = DEFAULT_UNITS[0]

# Limits taken from the column definitions in brauprotokoll.sql.
MAX_TYPE_LEN = 20
MAX_NAME_LEN = 100
MAX_UNIT_LEN = 20
MAX_ATTR_NAME_LEN = 255
MAX_ATTR_VALUE_LEN = 255
MAX_STOCK = Decimal("99999.99")  # numeric(7,2)


@dataclass
class AttributeInput:
    name: str = ""
    value: str = ""
    error: str | None = None

    def is_blank(self) -> bool:
        return not (self.name.strip() or self.value.strip())


@dataclass
class IngredientInput:
    ingredient_type: str = ""
    name: str = ""
    stock: str = ""
    unit: str = DEFAULT_UNIT
    attributes: list[AttributeInput] = field(default_factory=list)


@dataclass
class ValidatedIngredient:
    ingredient_type: str
    name: str
    stock: Decimal
    unit: str
    attributes: list[tuple[str, str]]


def _validate_stock(text: str) -> tuple[Decimal, str | None]:
    try:
        stock = parse_decimal(text)
    except ValueError:
        return Decimal("0"), "Bitte eine Zahl eingeben (z. B. 1,5)."
    if stock is None:
        return Decimal("0"), None
    if stock < 0:
        return stock, "Der Bestand darf nicht negativ sein."
    if stock > MAX_STOCK:
        return stock, "Der Bestand darf höchstens 99999,99 betragen."
    if stock != stock.quantize(Decimal("0.01")):
        return stock, "Höchstens zwei Nachkommastellen sind erlaubt."
    return stock, None


def validate(data: IngredientInput) -> tuple[dict[str, str], ValidatedIngredient | None]:
    """Validate the form input; error messages are attached to the input."""
    errors: dict[str, str] = {}

    data.ingredient_type = data.ingredient_type.strip()
    data.name = data.name.strip()
    data.unit = data.unit.strip() or DEFAULT_UNIT
    if not data.ingredient_type:
        errors["ingredient_type"] = "Bitte eine Rohstoffart angeben."
    elif len(data.ingredient_type) > MAX_TYPE_LEN:
        errors["ingredient_type"] = f"Höchstens {MAX_TYPE_LEN} Zeichen erlaubt."
    if not data.name:
        errors["name"] = "Bitte eine Bezeichnung angeben."
    elif len(data.name) > MAX_NAME_LEN:
        errors["name"] = f"Höchstens {MAX_NAME_LEN} Zeichen erlaubt."
    if len(data.unit) > MAX_UNIT_LEN:
        errors["unit"] = f"Höchstens {MAX_UNIT_LEN} Zeichen erlaubt."

    stock, stock_error = _validate_stock(data.stock)
    if stock_error:
        errors["stock"] = stock_error

    data.attributes = [a for a in data.attributes if not a.is_blank()]
    cleaned: list[tuple[str, str]] = []
    for attr in data.attributes:
        attr.error = None
        attr.name, attr.value = attr.name.strip(), attr.value.strip()
        if not (attr.name and attr.value):
            attr.error = "Name und Wert sind erforderlich."
        elif len(attr.name) > MAX_ATTR_NAME_LEN:
            attr.error = f"Der Name darf höchstens {MAX_ATTR_NAME_LEN} Zeichen haben."
        elif len(attr.value) > MAX_ATTR_VALUE_LEN:
            attr.error = f"Der Wert darf höchstens {MAX_ATTR_VALUE_LEN} Zeichen haben."
        else:
            cleaned.append((attr.name, attr.value))
        if attr.error:
            errors["attributes"] = "Bitte die markierten Eigenschaften korrigieren."

    if errors:
        return errors, None
    return errors, ValidatedIngredient(
        data.ingredient_type, data.name, stock, data.unit, cleaned
    )


def save_ingredient(
    session: Session, data: IngredientInput, ingredient_id: int | None = None
) -> tuple[Ingredient | None, dict[str, str]]:
    """Create or update an ingredient with its attributes in one transaction."""
    errors, valid = validate(data)
    if valid is None:
        return None, errors

    existing = repo.find_by_type_and_name(session, valid.ingredient_type, valid.name)
    if existing is not None and existing.ingredient_id != ingredient_id:
        return None, {"name": "Diesen Rohstoff gibt es in dieser Art bereits."}

    if ingredient_id is None:
        ingredient = Ingredient()
        session.add(ingredient)
    else:
        ingredient = repo.get(session, ingredient_id)
        if ingredient is None:
            return None, {"_general": "Der Rohstoff existiert nicht mehr."}

    ingredient.ingredient_type = valid.ingredient_type
    ingredient.name = valid.name
    ingredient.stock = valid.stock
    ingredient.unit = valid.unit
    ingredient.change_date = date.today()
    ingredient.attributes = [
        IngredientAttribute(attribute_name=n, attribute_value=v) for n, v in valid.attributes
    ]
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Saving ingredient failed")
        return None, {"_general": "Speichern fehlgeschlagen. Es wurde nichts geändert."}
    return ingredient, {}


def update_stock(session: Session, ingredient_id: int, stock_text: str) -> str | None:
    """Change only the stock; returns an error message or None."""
    ingredient = repo.get(session, ingredient_id)
    if ingredient is None:
        return "Der Rohstoff existiert nicht mehr."
    stock, error = _validate_stock(stock_text)
    if error:
        return error
    ingredient.stock = stock
    ingredient.change_date = date.today()
    try:
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Updating stock failed")
        return "Speichern fehlgeschlagen. Es wurde nichts geändert."
    return None


def delete_ingredient(session: Session, ingredient_id: int) -> str | None:
    """Delete an ingredient with its attributes; returns an error message or None."""
    ingredient = repo.get(session, ingredient_id)
    if ingredient is None:
        return "Der Rohstoff existiert nicht mehr."
    if repo.is_used_as_yeast(session, ingredient_id):
        return "Dieser Rohstoff wird in einem Brauprotokoll als Hefe verwendet und kann nicht gelöscht werden."
    try:
        session.delete(ingredient)
        session.commit()
    except SQLAlchemyError:
        session.rollback()
        logger.exception("Deleting ingredient failed")
        return "Löschen fehlgeschlagen. Es wurde nichts geändert."
    return None


def input_from_ingredient(ingredient: Ingredient) -> IngredientInput:
    return IngredientInput(
        ingredient_type=ingredient.ingredient_type,
        name=ingredient.name,
        stock=str(ingredient.stock if ingredient.stock is not None else ""),
        unit=ingredient.unit,
        attributes=[AttributeInput(a.attribute_name, a.attribute_value) for a in ingredient.attributes],
    )


def type_suggestions(session: Session) -> list[str]:
    return list(dict.fromkeys([*DEFAULT_TYPES, *repo.list_types(session)]))


def unit_suggestions(session: Session) -> list[str]:
    return list(dict.fromkeys([*DEFAULT_UNITS, *repo.list_units(session)]))


@dataclass
class OverviewRow:
    ingredient: Ingredient
    values: list[str]
    summary: str


@dataclass
class Overview:
    types: list[str]
    selected: str | None
    columns: list[str]
    rows: list[OverviewRow]


def build_overview(session: Session, selected: str | None) -> Overview:
    """Rows for the overview; a single type gets one column per attribute name."""
    ingredients = repo.list_ingredients(session, selected)
    columns = repo.attribute_names(session, selected) if selected else []
    rows = []
    for ingredient in ingredients:
        by_name = {a.attribute_name: a.attribute_value for a in ingredient.attributes}
        summary = ", ".join(f"{a.attribute_name}: {a.attribute_value}" for a in ingredient.attributes)
        rows.append(OverviewRow(ingredient, [by_name.get(c, "") for c in columns], summary))
    return Overview(repo.list_types(session), selected, columns, rows)
