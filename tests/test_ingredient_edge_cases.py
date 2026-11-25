from datetime import date

import pytest
from fastapi.testclient import TestClient

import app.main as main
from app.migrate import MigrationError
from app.services import ingredients as service
from app.services.ingredients import AttributeInput, IngredientInput


def _with_attribute(name, value):
    return IngredientInput("Hopfen", "X", "", "kg", [AttributeInput(name, value)])


def test_attribute_values_are_stored_as_entered_but_trimmed():
    errors, valid = service.validate(_with_attribute(" Alpha ", "  7,5  "))
    assert errors == {} and valid.attributes == [("Alpha", "7,5")]


@pytest.mark.parametrize(("name", "value"), [("A", ""), ("", "1"), ("A", "   ")])
def test_incomplete_attribute_is_rejected(name, value):
    errors, valid = service.validate(_with_attribute(name, value))
    assert valid is None and "attributes" in errors


def test_length_limits():
    data = IngredientInput("x" * 21, "y" * 101, "", "kg", [AttributeInput("n" * 256, "1")])
    errors, _ = service.validate(data)
    assert {"ingredient_type", "name", "attributes"} <= errors.keys()
    assert "attributes" in service.validate(_with_attribute("A", "v" * 256))[0]


def test_blank_attribute_rows_are_ignored():
    data = IngredientInput("Malz", "Pilsner", "", "kg", [AttributeInput(), AttributeInput("EBC", "3")])
    errors, valid = service.validate(data)
    assert errors == {} and len(valid.attributes) == 1


def test_unknown_ids_are_handled(session, client):
    assert service.update_stock(session, 999, "1") == "Der Rohstoff existiert nicht mehr."
    assert service.delete_ingredient(session, 999) == "Der Rohstoff existiert nicht mehr."
    _, errors = service.save_ingredient(session, IngredientInput("Malz", "A", ""), 999)
    assert errors == {"_general": "Der Rohstoff existiert nicht mehr."}
    assert client.get("/rohstoffe/999/bearbeiten").status_code == 404
    assert "existiert nicht mehr" in client.post("/rohstoffe/999/loeschen").text
    assert "existiert nicht mehr" in client.post("/rohstoffe/999/bestand", data={"stock": "1"}).text


def test_web_update_and_validation_error(client, session):
    client.post("/rohstoffe", data={"ingredient_type": "Malz", "name": "A", "stock": "1"})
    client.post("/rohstoffe", data={"ingredient_type": "Malz", "name": "B", "stock": "1"})
    first_id = service.repo.find_by_type_and_name(session, "Malz", "A").ingredient_id
    duplicate = client.post(f"/rohstoffe/{first_id}", data={"ingredient_type": "Malz", "name": "B", "stock": "1"})
    assert "gibt es in dieser Art bereits" in duplicate.text
    renamed = client.post(f"/rohstoffe/{first_id}", data={"ingredient_type": "Malz", "name": "C", "stock": "2"})
    assert "Rohstoff gespeichert." in renamed.text
    invalid_stock = client.post(f"/rohstoffe/{first_id}/bestand", data={"stock": "abc"})
    assert "Bitte eine Zahl eingeben" in invalid_stock.text


def test_stock_change_updates_change_date(session):
    ingredient, _ = service.save_ingredient(session, IngredientInput("Malz", "A", "1"))
    ingredient.change_date = date(2020, 1, 1)
    session.commit()
    service.update_stock(session, ingredient.ingredient_id, "2")
    session.refresh(ingredient)
    assert ingredient.change_date == date.today()


def test_startup_runs_migrations(monkeypatch):
    calls = []
    monkeypatch.setattr(main, "run_migrations", lambda: calls.append("migrated"))
    with TestClient(main.app) as client:
        assert client.get("/health").json() == {"status": "ok"}
    assert calls == ["migrated"]


def test_startup_aborts_when_migration_fails(monkeypatch):
    def failing():
        raise MigrationError("Database migration failed, application will not start: boom")

    monkeypatch.setattr(main, "run_migrations", failing)
    with pytest.raises(MigrationError, match="application will not start"):
        with TestClient(main.app):
            pass
