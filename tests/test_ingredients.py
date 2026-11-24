from datetime import date
from decimal import Decimal

from app.models import BrewingLog, Ingredient, Recipe
from app.services import ingredients as service
from app.services.ingredients import AttributeInput, IngredientInput


def _hop(**overrides) -> IngredientInput:
    data = IngredientInput(
        "Hopfen", "Perle", "1,5", [AttributeInput("Alpha", "decimal", "7,9")]
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


def test_save_creates_ingredient_with_normalised_values(session):
    ingredient, errors = service.save_ingredient(session, _hop())
    assert errors == {}
    assert ingredient.stock == Decimal("1.50")
    assert ingredient.change_date == date.today()
    assert [(a.attribute_name, a.attribute_value) for a in ingredient.attributes] == [("Alpha", "7.9")]


def test_validation_errors(session):
    data = IngredientInput("", "", "abc", [AttributeInput("Alpha", "decimal", "x"), AttributeInput("only name")])
    ingredient, errors = service.save_ingredient(session, data)
    assert ingredient is None
    assert {"ingredient_type", "name", "stock", "attributes"} <= errors.keys()
    assert all(a.error for a in data.attributes)


def test_stock_limits(session):
    assert "negativ" in service.validate(_hop(stock="-1"))[0]["stock"]
    assert "99,99" in service.validate(_hop(stock="100"))[0]["stock"]
    assert "Nachkomma" in service.validate(_hop(stock="1,234"))[0]["stock"]
    assert service.validate(_hop(stock=""))[1].stock == Decimal("0")


def test_duplicate_type_and_name_rejected(session):
    service.save_ingredient(session, _hop())
    ingredient, errors = service.save_ingredient(session, _hop())
    assert ingredient is None and "name" in errors


def test_update_replaces_attributes(session):
    ingredient, _ = service.save_ingredient(session, _hop())
    data = _hop(attributes=[AttributeInput("Herkunft", "text", "DE")])
    updated, errors = service.save_ingredient(session, data, ingredient.ingredient_id)
    assert errors == {}
    assert [a.attribute_name for a in updated.attributes] == ["Herkunft"]


def test_update_stock_and_delete(session):
    ingredient, _ = service.save_ingredient(session, _hop())
    assert service.update_stock(session, ingredient.ingredient_id, "2,25") is None
    assert session.get(Ingredient, ingredient.ingredient_id).stock == Decimal("2.25")
    assert service.update_stock(session, ingredient.ingredient_id, "x") is not None
    assert service.delete_ingredient(session, ingredient.ingredient_id) is None
    assert session.get(Ingredient, ingredient.ingredient_id) is None


def test_yeast_in_use_cannot_be_deleted(session):
    yeast, _ = service.save_ingredient(session, IngredientInput("Hefe", "US-05", "0"))
    recipe = Recipe(recipe_name="R")
    session.add(
        BrewingLog(
            recipe=recipe,
            yeast=yeast.ingredient_id,
            brewing_date=date.today(),
            plato_target=Decimal("12"),
            alcohol_target=Decimal("5"),
            temperature_fermentation=Decimal("13"),
            co2_target=Decimal("5.4"),
        )
    )
    session.commit()
    assert "verwendet" in service.delete_ingredient(session, yeast.ingredient_id)
    assert session.get(Ingredient, yeast.ingredient_id) is not None


def test_overview_columns_per_type(session):
    service.save_ingredient(session, _hop())
    service.save_ingredient(
        session, IngredientInput("Malz", "Pilsner", "5", [AttributeInput("EBC", "decimal", "3")])
    )
    overview = service.build_overview(session, "Hopfen")
    assert overview.columns == ["Alpha"]
    assert overview.rows[0].values == ["7,9"]
    assert len(service.build_overview(session, None).rows) == 2


def test_web_flow(client):
    assert client.get("/rohstoffe").status_code == 200
    response = client.post(
        "/rohstoffe",
        data={
            "ingredient_type": "Malz",
            "name": "Wiener",
            "stock": "2,5",
            "attr_name": ["EBC"],
            "attr_datatype": ["decimal"],
            "attr_value": ["6,5"],
        },
    )
    assert "Rohstoff gespeichert." in response.text and "Wiener" in response.text
    assert "6,5" in client.get("/rohstoffe?art=Malz").text

    invalid = client.post("/rohstoffe", data={"ingredient_type": "Malz", "name": "", "stock": "x"})
    assert "Bitte eine Bezeichnung angeben." in invalid.text

    suggestions = client.get("/rohstoffe/vorschlaege", params={"ingredient_type": "Malz"})
    assert 'value="EBC"' in suggestions.text

    page = client.get("/rohstoffe/1/bearbeiten")
    assert 'value="Wiener"' in page.text and 'value="2,50"' in page.text

    assert "Bestand gespeichert." in client.post("/rohstoffe/1/bestand", data={"stock": "3"}).text
    assert "Rohstoff gelöscht." in client.post("/rohstoffe/1/loeschen").text
