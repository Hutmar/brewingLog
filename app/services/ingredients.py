"""Business logic for the ingredient management."""
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import Ingredient, IngredientAttribute
from app.parsing import parse_decimal
from app.repositories import ingredients as repo

logger = logging.getLogger(__name__)

DEFAULT_TYPES = ("Malz", "Hopfen", "Hefe")

# Limits taken from the column definitions in brauprotokoll.sql.
MAX_TYPE_LEN = 20
MAX_NAME_LEN = 100
MAX_ATTR_NAME_LEN = 255
MAX_ATTR_DATATYPE_LEN = 50
MAX_ATTR_VALUE_LEN = 255
MAX_STOCK = Decimal("99.99")  # numeric(4,2)

# attribute_datatype is free text; these well-known names get their value
# validated and normalised, all other datatypes are stored as entered.
NUMERIC_DATATYPES = {"decimal", "number", "numeric", "float", "zahl", "dezimal"}
INTEGER_DATATYPES = {"integer", "int", "ganzzahl"}
DATE_DATATYPES = {"date", "datum"}


def is_numeric_datatype(datatype: str) -> bool:
    return datatype.strip().lower() in NUMERIC_DATATYPES


@dataclass
class AttributeInput:
    name: str = ""
    datatype: str = ""
    value: str = ""
    error: str | None = None

    def is_blank(self) -> bool:
        return not (self.name.strip() or self.datatype.strip() or self.value.strip())


@dataclass
class IngredientInput:
    ingredient_type: str = ""
    name: str = ""
    stock: str = ""
    attributes: list[AttributeInput] = field(default_factory=list)


@dataclass
class ValidatedIngredient:
    ingredient_type: str
    name: str
    stock: Decimal
    attributes: list[tuple[str, str, str]]


def _normalise_attribute_value(datatype: str, value: str) -> str:
    kind = datatype.strip().lower()
    if kind in NUMERIC_DATATYPES:
        try:
            number = parse_decimal(value)
        except ValueError:
            raise ValueError("Bitte eine Zahl eingeben.") from None
        return format(number, "f")
    if kind in INTEGER_DATATYPES:
        try:
            return str(int(value.strip()))
        except ValueError:
            raise ValueError("Bitte eine ganze Zahl eingeben.") from None
    if kind in DATE_DATATYPES:
        try:
            return date.fromisoformat(value.strip()).isoformat()
        except ValueError:
            try:
                return datetime.strptime(value.strip(), "%d.%m.%Y").date().isoformat()
            except ValueError:
                raise ValueError("Bitte ein Datum eingeben (TT.MM.JJJJ).") from None
    return value.strip()


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
        return stock, "Der Bestand darf höchstens 99,99 kg betragen."
    if stock != stock.quantize(Decimal("0.01")):
        return stock, "Höchstens zwei Nachkommastellen sind erlaubt."
    return stock, None


def validate(data: IngredientInput) -> tuple[dict[str, str], ValidatedIngredient | None]:
    """Validate the form input; error messages are attached to the input."""
    errors: dict[str, str] = {}

    data.ingredient_type = data.ingredient_type.strip()
    data.name = data.name.strip()
    if not data.ingredient_type:
        errors["ingredient_type"] = "Bitte eine Rohstoffart angeben."
    elif len(data.ingredient_type) > MAX_TYPE_LEN:
        errors["ingredient_type"] = f"Höchstens {MAX_TYPE_LEN} Zeichen erlaubt."
    if not data.name:
        errors["name"] = "Bitte eine Bezeichnung angeben."
    elif len(data.name) > MAX_NAME_LEN:
        errors["name"] = f"Höchstens {MAX_NAME_LEN} Zeichen erlaubt."

    stock, stock_error = _validate_stock(data.stock)
    if stock_error:
        errors["stock"] = stock_error

    data.attributes = [a for a in data.attributes if not a.is_blank()]
    cleaned: list[tuple[str, str, str]] = []
    for attr in data.attributes:
        attr.error = None
        attr.name, attr.datatype = attr.name.strip(), attr.datatype.strip()
        if not (attr.name and attr.datatype and attr.value.strip()):
            attr.error = "Name, Datentyp und Wert sind erforderlich."
        elif len(attr.name) > MAX_ATTR_NAME_LEN or len(attr.datatype) > MAX_ATTR_DATATYPE_LEN:
            attr.error = "Name oder Datentyp ist zu lang."
        else:
            try:
                value = _normalise_attribute_value(attr.datatype, attr.value)
            except ValueError as exc:
                attr.error = str(exc)
            else:
                if len(value) > MAX_ATTR_VALUE_LEN:
                    attr.error = f"Der Wert darf höchstens {MAX_ATTR_VALUE_LEN} Zeichen haben."
                else:
                    cleaned.append((attr.name, attr.datatype, value))
        if attr.error:
            errors["attributes"] = "Bitte die markierten Eigenschaften korrigieren."

    if errors:
        return errors, None
    return errors, ValidatedIngredient(data.ingredient_type, data.name, stock, cleaned)


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
    ingredient.change_date = date.today()
    ingredient.attributes = [
        IngredientAttribute(attribute_name=n, attribute_datatype=t, attribute_value=v)
        for n, t, v in valid.attributes
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
        attributes=[
            AttributeInput(a.attribute_name, a.attribute_datatype, a.attribute_value)
            for a in ingredient.attributes
        ],
    )


def type_suggestions(session: Session) -> list[str]:
    return list(dict.fromkeys([*DEFAULT_TYPES, *repo.list_types(session)]))


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


def _display_value(attr: IngredientAttribute) -> str:
    if is_numeric_datatype(attr.attribute_datatype):
        return attr.attribute_value.replace(".", ",")
    return attr.attribute_value


def build_overview(session: Session, selected: str | None) -> Overview:
    """Rows for the overview; a single type gets one column per attribute name."""
    ingredients = repo.list_ingredients(session, selected)
    columns = repo.attribute_names(session, selected) if selected else []
    rows = []
    for ingredient in ingredients:
        by_name = {a.attribute_name: _display_value(a) for a in ingredient.attributes}
        summary = ", ".join(f"{a.attribute_name}: {_display_value(a)}" for a in ingredient.attributes)
        rows.append(OverviewRow(ingredient, [by_name.get(c, "") for c in columns], summary))
    return Overview(repo.list_types(session), selected, columns, rows)
