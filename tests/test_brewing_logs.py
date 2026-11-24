from datetime import date
from decimal import Decimal as D

import pytest

from app.models import BrewingLog, Ingredient, Rating, Recipe
from app.services import brewing_logs as service


@pytest.fixture
def log_id(session):
    yeast = Ingredient(ingredient_type="Hefe", name="Diamond", change_date=date.today())
    first = BrewingLog(
        recipe=Recipe(recipe_name="Citra"),
        yeast_ingredient=yeast,
        brewing_date=date(2026, 3, 1),
        plato_target=D("14"),
        plato_after_boiling=D("13.6"),
        plato_current=D("3"),
        alcohol_target=D("5.7"),
        volume_after_fermentation=D("19"),
        temperature_fermentation=D("13"),
        co2_target=D("5.4"),
        bottling_volume=D("20.4"),
        bottling_date=date(2026, 3, 13),
        lagering_startdate=date(2026, 3, 23),
        ratings=[Rating(rating=8, remark="Fruchtig")],
    )
    second = BrewingLog(
        recipe=Recipe(recipe_name="Märzen"),
        yeast_ingredient=yeast,
        brewing_date=date(2026, 5, 1),
        plato_target=D("13.5"),
        alcohol_target=D("5.5"),
        temperature_fermentation=D("13"),
        co2_target=D("5.4"),
    )
    session.add_all([first, second])
    session.commit()
    log_id = first.brewing_log_id
    # Reload from the database so values carry the column scale, as in production.
    session.expunge_all()
    return log_id


def _rows(detail):
    return {row.label: row for group in detail.groups for row in group.rows}


def test_overview_sorted_by_date_descending(session, log_id):
    rows = service.build_overview(session)
    assert [r.recipe_name for r in rows] == ["Märzen", "Citra"]
    citra = rows[1]
    assert (citra.brewing_date, citra.bottling_volume, citra.rating) == ("01.03.2026", "20,4 l", "8")
    assert rows[0].rating == "–"


def test_detail_contains_stored_and_calculated_values(session, log_id):
    rows = _rows(service.build_detail(session, log_id))
    assert rows["Rezept"].value == "Citra"
    assert rows["Hefe"].value == "Diamond"
    assert rows["Geschmack"].value == "Fruchtig"
    assert (rows["Alkoholgehalt vor Nachgärung"].value, rows["Alkoholgehalt vor Nachgärung"].calculated) == ("5,68 % vol", True)
    assert rows["Verdünnung (berechnet)"].value == "1,4 l"
    assert rows["Alkoholgehalt nach Nachgärung"].value == "5,70 % vol"
    assert rows["Zucker pro 0,5-l-Flasche"].value == "3,34 g"
    assert rows["Zucker pro 0,33-l-Flasche"].value == "2,23 g"
    assert (rows["Zucker gesamt"].value, rows["Zucker gesamt"].calculated) == ("136 g", True)
    assert rows["Zieldruck"].value == "1,6 bar"
    assert rows["Dauer Hauptgärung"].value == "12 Tage"
    assert rows["Dauer Reifung"].value == "10 Tage"
    assert rows["Dauer gesamt"].value == "36 Tage"


def test_detail_shows_dash_for_missing_values(session, log_id):
    second_id = log_id + 1
    rows = _rows(service.build_detail(session, second_id))
    assert rows["Stammwürze vor Kochen"].value == "–"
    assert rows["Dauer gesamt"].value == "–"
    assert rows["Alkoholgehalt vor Nachgärung"].value == "–"


def test_missing_log_returns_none(session):
    assert service.build_detail(session, 999) is None


def test_pages(client, log_id):
    page = client.get("/protokoll")
    assert page.status_code == 200
    assert "Citra" in page.text and f"/protokoll/{log_id}" in page.text
    detail = client.get(f"/protokoll/{log_id}")
    assert detail.status_code == 200
    assert "Alkohol und Verdünnung" in detail.text and "berechnet" in detail.text
    assert client.get("/protokoll/999").status_code == 404
    assert client.get("/").url.path == "/protokoll"
