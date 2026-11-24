"""Schema behaviour that must hold on every supported database."""
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import BrewingLog, Ingredient, Rating, Recipe


def _log(**overrides) -> BrewingLog:
    values = dict(
        recipe=Recipe(recipe_name="R"),
        yeast_ingredient=Ingredient(ingredient_type="Hefe", name="Y", change_date=date.today()),
        brewing_date=date.today(),
        plato_target=D("12.5"),
        alcohol_target=D("5.50"),
        temperature_fermentation=D("13"),
        co2_target=D("5.4"),
    )
    values.update(overrides)
    return BrewingLog(**values)


def test_ids_and_defaults_are_assigned(session):
    log = _log(ratings=[Rating(rating=8, remark="good")])
    session.add(log)
    session.commit()
    assert log.brewing_log_id and log.recipe.recipe_id and log.ratings[0].rating_id
    assert log.yeast_ingredient.stock == D("0")
    assert log.water_addition_boiling == D("0")


def test_ids_are_unique_across_rows(session):
    session.add_all([Recipe(recipe_name="A"), Recipe(recipe_name="B"), Recipe(recipe_name="C")])
    session.commit()
    ids = [r.recipe_id for r in session.query(Recipe).all()]
    assert len(set(ids)) == 3


def test_rating_range_is_enforced(session):
    session.add(_log(ratings=[Rating(rating=11)]))
    with pytest.raises(IntegrityError):
        session.flush()


def test_unique_constraints(session):
    session.add(Recipe(recipe_name="Same"))
    session.commit()
    session.add(Recipe(recipe_name="Same"))
    with pytest.raises(IntegrityError):
        session.flush()
    session.rollback()

    session.add(Ingredient(ingredient_type="Malz", name="X", change_date=date.today()))
    session.commit()
    session.add(Ingredient(ingredient_type="Malz", name="X", change_date=date.today()))
    with pytest.raises(IntegrityError):
        session.flush()


def test_required_columns_are_enforced(session):
    session.add(_log(plato_target=None))
    with pytest.raises(IntegrityError):
        session.flush()
