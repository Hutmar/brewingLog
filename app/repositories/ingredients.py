"""Database access for ingredients and their attributes."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import BrewingLog, Ingredient, IngredientAttribute


def list_types(session: Session) -> list[str]:
    stmt = select(Ingredient.ingredient_type).distinct().order_by(Ingredient.ingredient_type)
    return list(session.scalars(stmt))


def list_ingredients(session: Session, ingredient_type: str | None = None) -> list[Ingredient]:
    stmt = (
        select(Ingredient)
        .options(selectinload(Ingredient.attributes))
        .order_by(Ingredient.ingredient_type, Ingredient.name)
    )
    if ingredient_type:
        stmt = stmt.where(Ingredient.ingredient_type == ingredient_type)
    return list(session.scalars(stmt))


def get(session: Session, ingredient_id: int) -> Ingredient | None:
    return session.get(Ingredient, ingredient_id)


def find_by_type_and_name(
    session: Session, ingredient_type: str, name: str
) -> Ingredient | None:
    stmt = select(Ingredient).where(
        Ingredient.ingredient_type == ingredient_type, Ingredient.name == name
    )
    return session.scalars(stmt).first()


def _attribute_column_values(session: Session, column, ingredient_type: str | None) -> list[str]:
    stmt = select(column).distinct().order_by(column)
    if ingredient_type:
        stmt = stmt.join(Ingredient).where(Ingredient.ingredient_type == ingredient_type)
    return list(session.scalars(stmt))


def attribute_names(session: Session, ingredient_type: str | None) -> list[str]:
    return _attribute_column_values(session, IngredientAttribute.attribute_name, ingredient_type)


def list_units(session: Session) -> list[str]:
    stmt = select(Ingredient.unit).distinct().order_by(Ingredient.unit)
    return list(session.scalars(stmt))


def is_used_as_yeast(session: Session, ingredient_id: int) -> bool:
    stmt = select(BrewingLog.brewing_log_id).where(BrewingLog.yeast == ingredient_id).limit(1)
    return session.scalars(stmt).first() is not None
