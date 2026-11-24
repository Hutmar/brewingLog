from datetime import date
from decimal import Decimal as D

import pytest

from app.models import BrewingLog, Ingredient, Rating, Recipe
from app.services import brewing_log_form as form


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
        "plato_after_boiling": "13,6",
        "plato_current": "3",
        "yeast": str(yeast_row.ingredient_id),
        "temperature_fermentation": "13",
        "alcohol_target": "5,7",
        "volume_after_fermentation": "19",
        "co2_target": "5,4",
        "bottling_date": "2026-03-13",
        "lagering_startdate": "2026-03-23",
    }
    raw.update(overrides)
    return raw


def test_empty_fields_are_filled_with_calculated_values(session, yeast):
    log, errors = form.save(session, _raw(yeast))
    assert errors == {}
    assert log.recipe.recipe_name == "Citra"
    assert log.alcohol_before_sec_fermentation == D("5.68")
    assert log.water_addition_fermentation == D("1.4")
    assert log.bottling_volume == D("20.4")
    assert log.alcohol_after_sec_fermentation == D("5.7")
    assert log.sugar_total == D("136")
    assert log.water_addition_boiling == D("0")
    assert log.ratings == []


def test_entered_values_override_calculation(session, yeast):
    log, errors = form.save(
        session, _raw(yeast, water_addition_fermentation="2", sugar_total="150", bottling_volume="21")
    )
    assert errors == {}
    assert (log.water_addition_fermentation, log.sugar_total, log.bottling_volume) == (D("2.0"), D("150.0"), D("21.0"))


def test_required_fields_and_ranges(session, yeast):
    raw = _raw(yeast, recipe_name=" ", plato_target="", alcohol_target="10", water_addition_boiling="10",
               co2_target="5,45", temperature_fermentation="x", rating="11", brewing_date="")
    log, errors = form.save(session, raw)
    assert log is None
    assert set(errors) == {"recipe_name", "plato_target", "alcohol_target", "water_addition_boiling",
                           "co2_target", "temperature_fermentation", "rating", "brewing_date"}


def test_yeast_must_exist_and_be_a_yeast(session, yeast):
    malt = Ingredient(ingredient_type="Malz", name="Wiener", change_date=date.today())
    session.add(malt)
    session.commit()
    assert "yeast" in form.save(session, _raw(yeast, yeast=str(malt.ingredient_id)))[1]
    assert "yeast" in form.save(session, _raw(yeast, yeast=""))[1]


def test_calculated_value_outside_column_range_is_reported(session, yeast):
    # 19 l at 5.7 % target with alcohol 1.0 % needs far more than 9.9 l of "dilution".
    raw = _raw(yeast, alcohol_before_sec_fermentation="30", alcohol_target="1")
    _, errors = form.save(session, raw)
    assert "water_addition_fermentation" in errors


def test_recipe_is_reused_and_rating_is_managed(session, yeast):
    first, _ = form.save(session, _raw(yeast, rating="8", remark="Fruchtig"))
    assert first.ratings[0].rating == 8
    second, _ = form.save(session, _raw(yeast, brewing_date="2026-06-01"))
    assert second.recipe_id == first.recipe_id
    assert session.query(Recipe).count() == 1

    updated, errors = form.save(session, _raw(yeast, rating="", remark=""), first.brewing_log_id)
    assert errors == {} and updated.ratings == []
    assert session.query(Rating).count() == 0


def test_edit_roundtrip_prefills_stored_values(session, yeast):
    log, _ = form.save(session, _raw(yeast, rating="7", remark="ok", deviations="mehr Hopfen"))
    log_id = log.brewing_log_id
    session.expunge_all()  # load from the database like a real edit request
    raw = form.input_from_log(form.repo.get(session, log_id))
    assert raw["recipe_name"] == "Citra" and raw["brewing_date"] == "2026-03-01"
    assert raw["plato_target"] == "14,0" and raw["rating"] == "7" and raw["deviations"] == "mehr Hopfen"
    again, errors = form.save(session, raw, log_id)
    assert errors == {} and again.plato_target == D("14.0")


def test_delete_removes_log_and_rating(session, yeast):
    log, _ = form.save(session, _raw(yeast, rating="8"))
    assert form.delete(session, log.brewing_log_id) is None
    assert session.query(BrewingLog).count() == 0 and session.query(Rating).count() == 0
    assert form.delete(session, log.brewing_log_id) is not None


def test_web_flow(client, session, yeast):
    assert "Hefe" in client.get("/protokoll/neu").text
    response = client.post("/protokoll", data=_raw(yeast, rating="9"))
    assert "Sud gespeichert." in response.text and "Citra" in response.text

    invalid = client.post("/protokoll", data=_raw(yeast, plato_target=""))
    assert "Pflichtfeld." in invalid.text and 'value="Citra"' in invalid.text

    live = client.post("/protokoll/berechnen", data=_raw(yeast))
    assert "3,34 g" in live.text and 'id="hint-water_addition_fermentation"' in live.text
    assert "Berechnet: 1,4 l" in live.text

    edit = client.get("/protokoll/1/bearbeiten")
    assert 'value="Citra"' in edit.text and "selected" in edit.text

    assert "Sud gespeichert." in client.post("/protokoll/1", data=_raw(yeast, deviations="x")).text
    assert "Sud gelöscht." in client.post("/protokoll/1/loeschen").text
    assert client.get("/protokoll/1/bearbeiten").status_code == 404
