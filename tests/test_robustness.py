"""Transaction safety, logging and input edge cases."""
import logging
from datetime import date
from decimal import Decimal as D

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models import BrewingLog, Ingredient, Rating, Recipe
from app.services import brewing_log_form as log_form
from app.services import ingredients as ingredient_service
from app.services.ingredients import AttributeInput, IngredientInput


@pytest.fixture
def failing_commit(session, monkeypatch):
    def boom():
        raise SQLAlchemyError("simulated failure")

    monkeypatch.setattr(session, "commit", boom)


@pytest.fixture
def yeast(session):
    ingredient = Ingredient(ingredient_type="Hefe", name="Diamond", change_date=date.today())
    session.add(ingredient)
    session.commit()
    return ingredient


def _raw(yeast_row, **overrides):
    raw = {
        "recipe_name": "Citra",
        "brewing_date": "2026-03-01",
        "plato_target": "14",
        "yeast": str(yeast_row.ingredient_id),
        "temperature_fermentation": "13",
        "alcohol_target": "5.7",
        "co2_target": "5.4",
        "rating": "8",
    }
    raw.update(overrides)
    return raw


def test_failed_ingredient_save_leaves_nothing_behind(session, failing_commit, caplog):
    data = IngredientInput("Hopfen", "Perle", "1", "kg", [AttributeInput("Alpha", "7")])
    with caplog.at_level(logging.ERROR):
        ingredient, errors = ingredient_service.save_ingredient(session, data)
    assert ingredient is None and "_general" in errors
    assert "Saving ingredient failed" in caplog.text
    assert session.query(Ingredient).count() == 0


def test_failed_brewing_log_save_leaves_nothing_behind(session, yeast, failing_commit, caplog):
    with caplog.at_level(logging.ERROR):
        log, errors = log_form.save(session, _raw(yeast))
    assert log is None and "_general" in errors
    assert "Saving brewing log failed" in caplog.text
    assert session.query(BrewingLog).count() == 0
    assert session.query(Recipe).count() == 0
    assert session.query(Rating).count() == 0


def test_failed_delete_is_reported_and_logged(session, yeast, caplog):
    log, _ = log_form.save(session, _raw(yeast))
    session.commit = lambda: (_ for _ in ()).throw(SQLAlchemyError("simulated failure"))
    with caplog.at_level(logging.ERROR):
        error = log_form.delete(session, log.brewing_log_id)
    assert error and "Deleting brewing log failed" in caplog.text
    session.rollback()
    assert session.query(BrewingLog).count() == 1


@pytest.mark.parametrize("stock", ["1.5", "1,5", " 1,50 "])
def test_stock_accepts_both_decimal_separators(session, stock):
    ingredient, errors = ingredient_service.save_ingredient(
        session, IngredientInput("Malz", "Pilsner", stock)
    )
    assert errors == {} and ingredient.stock == D("1.5")


def test_brewing_log_accepts_dot_and_comma(session, yeast):
    first, e1 = log_form.save(session, _raw(yeast, alcohol_target="5.7"))
    second, e2 = log_form.save(session, _raw(yeast, recipe_name="Other", alcohol_target="5,7"))
    assert e1 == e2 == {}
    assert first.alcohol_target == second.alcohol_target == D("5.7")


def test_texts_are_trimmed_and_length_limited(session, yeast):
    log, errors = log_form.save(session, _raw(yeast, recipe_name="  Citra  ", deviations="x" * 2001))
    assert log is None and "deviations" in errors
    log, errors = log_form.save(session, _raw(yeast, recipe_name="  Citra  "))
    assert errors == {} and log.recipe.recipe_name == "Citra"


def test_implausible_dates_are_rejected(session, yeast):
    _, errors = log_form.save(session, _raw(yeast, brewing_date="31.02.2026", bottling_date="morgen"))
    assert {"brewing_date", "bottling_date"} <= errors.keys()


def test_german_date_format_is_accepted(session, yeast):
    log, errors = log_form.save(session, _raw(yeast, brewing_date="01.03.2026"))
    assert errors == {} and log.brewing_date == date(2026, 3, 1)


def test_live_calculation_tolerates_garbage(client, yeast):
    response = client.post("/protokoll/berechnen", data={"plato_target": "abc", "alcohol_target": "!!"})
    assert response.status_code == 200
    assert "–" in response.text


def test_yeast_in_use_cannot_be_deleted_via_web(client, session, yeast):
    log_form.save(session, _raw(yeast))
    response = client.post(f"/rohstoffe/{yeast.ingredient_id}/loeschen", data={"art": "Hefe"})
    assert "kann nicht gelöscht werden" in response.text
    assert session.get(Ingredient, yeast.ingredient_id) is not None


def test_html_in_input_is_escaped(client):
    response = client.post(
        "/rohstoffe", data={"ingredient_type": "Malz", "name": "<script>alert(1)</script>", "stock": "1"}
    )
    assert "<script>alert(1)</script>" not in response.text
    assert "&lt;script&gt;" in response.text


def test_unexpected_error_is_logged(client, caplog):
    from app.db import get_session
    from app.main import app

    def broken():
        raise RuntimeError("database down")
        yield

    app.dependency_overrides[get_session] = broken
    with caplog.at_level(logging.ERROR):
        response = client.get("/protokoll")
    assert response.status_code == 500
    assert "Unhandled error for GET /protokoll" in caplog.text
