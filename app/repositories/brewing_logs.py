"""Database access for brewing logs."""
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import BrewingLog, Ingredient, Recipe

YEAST_TYPE = "Hefe"


def _with_relations():
    return (
        joinedload(BrewingLog.recipe),
        joinedload(BrewingLog.yeast_ingredient),
        selectinload(BrewingLog.ratings),
    )


def list_logs(session: Session) -> list[BrewingLog]:
    stmt = (
        select(BrewingLog)
        .options(*_with_relations())
        .order_by(BrewingLog.brewing_date.desc(), BrewingLog.brewing_log_id.desc())
    )
    return list(session.scalars(stmt))


def list_recipe_names(session: Session) -> list[str]:
    return list(session.scalars(select(Recipe.recipe_name).order_by(Recipe.recipe_name)))


def find_recipe(session: Session, recipe_name: str) -> Recipe | None:
    return session.scalars(select(Recipe).where(Recipe.recipe_name == recipe_name)).first()


def list_yeasts(session: Session) -> list[Ingredient]:
    stmt = (
        select(Ingredient)
        .where(Ingredient.ingredient_type == YEAST_TYPE)
        .order_by(Ingredient.name)
    )
    return list(session.scalars(stmt))


def get_ingredient(session: Session, ingredient_id: int) -> Ingredient | None:
    return session.get(Ingredient, ingredient_id)


def get(session: Session, brewing_log_id: int) -> BrewingLog | None:
    stmt = (
        select(BrewingLog)
        .options(*_with_relations())
        .where(BrewingLog.brewing_log_id == brewing_log_id)
    )
    return session.scalars(stmt).first()
