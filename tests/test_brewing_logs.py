from datetime import date
from decimal import Decimal as D

import pytest

from app.models import BrewingLog, Ingredient, Rating, Recipe
from app.services import brewing_logs as service
from app.services.brewing_logs import ViewPrefs

TODAY = date(2026, 4, 15)


def _log(yeast, name, brewing_date, **extra):
    values = dict(
        plato_target=D("13.5"),
        alcohol_target=D("5.5"),
        temperature_fermentation=D("13"),
        co2_target=D("5.4"),
    )
    values.update(extra)
    return BrewingLog(
        recipe=Recipe(recipe_name=name),
        yeast_ingredient=yeast,
        brewing_date=brewing_date,
        **values,
    )


@pytest.fixture
def log_id(session):
    """Three brews: Citra is done, Dunkel is maturing, Märzen is still fermenting on TODAY."""
    yeast = Ingredient(ingredient_type="Hefe", name="Diamond", change_date=date.today())
    citra = _log(
        yeast, "Citra", date(2026, 3, 1),
        plato_target=D("14"),
        plato_after_boiling=D("13.6"),
        plato_current=D("3"),
        alcohol_target=D("5.7"),
        alcohol_after_sec_fermentation=D("5.7"),
        volume_after_fermentation=D("19"),
        pressure_current=D("1.6"),
        bottling_volume=D("20.4"),
        bottling_date=date(2026, 3, 13),
        lagering_startdate=date(2026, 3, 23),
        ratings=[Rating(rating=8, remark="Fruchtig")],
    )
    dunkel = _log(
        yeast, "Dunkel", date(2026, 4, 1),
        bottling_date=date(2026, 4, 8), lagering_startdate=date(2026, 4, 10),
    )
    maerzen = _log(yeast, "Märzen", date(2026, 5, 1))
    session.add_all([citra, dunkel, maerzen])
    session.commit()
    log_id = citra.brewing_log_id
    # Reload from the database so values carry the column scale, as in production.
    session.expunge_all()
    return log_id


def _rows(detail):
    return {row.label: row for group in detail.groups for row in group.rows}


def _names(overview):
    return [r.recipe_name for r in overview.rows]


def test_overview_default_is_newest_first(session, log_id):
    overview = service.build_overview(session, ViewPrefs(), TODAY)
    assert _names(overview) == ["Märzen", "Dunkel", "Citra"]
    citra = overview.rows[2]
    assert (citra.brewing_date, citra.end_date, citra.bottling_volume, citra.rating) == (
        "01.03.2026", "06.04.2026", "20,4 l", "8",
    )
    assert citra.alcohol == "5,70 % vol"
    assert overview.rows[0].rating == "–" and overview.rows[0].end_date == "–"


def test_overview_status(session, log_id):
    rows = {r.recipe_name: r for r in service.build_overview(session, ViewPrefs(), TODAY).rows}
    assert rows["Märzen"].status == "fermenting"
    assert rows["Dunkel"].status == "maturing"
    assert rows["Citra"].status == "done"
    assert rows["Citra"].status_label == "Abgeschlossen"


@pytest.mark.parametrize(
    ("sort", "direction", "expected"),
    [
        ("recipe", "asc", ["Citra", "Dunkel", "Märzen"]),
        ("recipe", "desc", ["Märzen", "Dunkel", "Citra"]),
        ("date", "asc", ["Citra", "Dunkel", "Märzen"]),
        ("status", "asc", ["Märzen", "Dunkel", "Citra"]),
        ("status", "desc", ["Citra", "Dunkel", "Märzen"]),
    ],
)
def test_overview_sorting(session, log_id, sort, direction, expected):
    overview = service.build_overview(session, ViewPrefs("", sort, direction), TODAY)
    assert _names(overview) == expected


def test_sort_columns_toggle_direction(session, log_id):
    columns = service.build_overview(session, ViewPrefs("", "recipe", "asc"), TODAY).columns
    assert (columns["recipe"].next_direction, columns["recipe"].indicator) == ("desc", "▲")
    assert (columns["date"].next_direction, columns["date"].indicator) == ("asc", "")
    columns = service.build_overview(session, ViewPrefs(), TODAY).columns
    assert (columns["date"].next_direction, columns["date"].indicator) == ("asc", "▼")


@pytest.mark.parametrize(
    ("search", "expected"),
    [("citr", ["Citra"]), ("CITRA", ["Citra"]), ("märz", ["Märzen"]), ("zzz", []), ("%", []), ("_", [])],
)
def test_overview_search_is_case_insensitive_and_literal(session, log_id, search, expected):
    assert _names(service.build_overview(session, ViewPrefs(search), TODAY)) == expected


def test_view_prefs_cookie_roundtrip_and_fallbacks():
    prefs = ViewPrefs("Märzen & Co", "recipe", "asc")
    assert ViewPrefs.from_cookie(prefs.to_cookie()) == prefs
    assert ViewPrefs.from_cookie(None) == ViewPrefs()
    assert ViewPrefs.from_cookie("not json") == ViewPrefs()
    tampered = ViewPrefs.from_cookie(ViewPrefs("x", "bogus", "sideways").to_cookie())
    assert (tampered.sort, tampered.direction) == ("date", "desc")
    base = ViewPrefs("old", "recipe", "asc")
    assert ViewPrefs.build(None, "status", None, base) == ViewPrefs("old", "status", "asc")
    assert ViewPrefs.build("", None, None, base).q == ""
    assert len(ViewPrefs.build("x" * 500, None, None, base).q) == 100


def test_detail_contains_stored_and_calculated_values(session, log_id):
    detail = service.build_detail(session, log_id, TODAY)
    rows = _rows(detail)
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
    assert (rows["CO₂ Ist"].value, rows["CO₂ Ist"].calculated) == ("5,3 g/l", True)
    assert rows["Druck Ist"].value == "1,60 bar"
    assert rows["Dauer Hauptgärung"].value == "12 Tage"
    assert rows["Dauer Reifung"].value == "10 Tage"
    assert rows["Dauer gesamt"].value == "36 Tage"
    assert (rows["Enddatum"].value, rows["Enddatum"].calculated) == ("06.04.2026", True)
    assert rows["Status"].value == "Abgeschlossen"
    assert "Alkoholgehalt aktuell" not in rows


def test_detail_groups_put_rating_last_and_separate_from_carbonation(session, log_id):
    titles = [g.title for g in service.build_detail(session, log_id, TODAY).groups]
    assert titles[-1] == "Bewertung"
    assert "Karbonisierung" in titles and "Geschmack und Karbonisierung" not in titles
    rating_group = service.build_detail(session, log_id, TODAY).groups[-1]
    assert [r.label for r in rating_group.rows] == ["Bewertung (1–10)", "Geschmack"]


def test_detail_shows_dash_for_missing_values(session, log_id):
    rows = _rows(service.build_detail(session, log_id + 2, TODAY))
    assert rows["Stammwürze vor Kochen"].value == "–"
    assert rows["Dauer gesamt"].value == "–"
    assert rows["Enddatum"].value == "–"
    assert rows["Alkoholgehalt vor Nachgärung"].value == "–"
    assert rows["Status"].value == "In Gärung"


def test_missing_log_returns_none(session):
    assert service.build_detail(session, 999) is None


def test_pages(client, log_id):
    page = client.get("/protokoll")
    assert page.status_code == 200
    assert "Citra" in page.text and f"/protokoll/{log_id}" in page.text
    assert "/loeschen" not in page.text
    detail = client.get(f"/protokoll/{log_id}")
    assert detail.status_code == 200
    assert "Alkohol und Verdünnung" in detail.text and "berechnet" in detail.text
    assert "/loeschen" not in detail.text
    assert client.get("/protokoll/999").status_code == 404
    assert client.get("/").url.path == "/protokoll"


def test_overview_page_has_status_icons_and_sort_links(client, log_id):
    page = client.get("/protokoll").text
    assert page.count('class="status status-') == 3
    assert 'hx-get="/protokoll/tabelle?sort=status&amp;dir=asc"' in page
    assert 'hx-get="/protokoll/tabelle?sort=recipe&amp;dir=asc"' in page
    # The date column is the active sort (descending), so the next click reverses it.
    assert 'hx-get="/protokoll/tabelle?sort=date&amp;dir=asc"' in page
    assert 'name="q"' in page and 'hx-trigger="input changed delay:300ms' in page


def test_table_fragment_and_persisted_view(client, log_id):
    fragment = client.get("/protokoll/tabelle", params={"q": "citr", "sort": "recipe", "dir": "asc"})
    assert fragment.status_code == 200
    assert '<div id="log-table">' in fragment.text and "<html" not in fragment.text
    assert "Citra" in fragment.text and "Märzen" not in fragment.text

    # A later full page load restores search text and sort order from the session cookie.
    page = client.get("/protokoll").text
    assert 'value="citr"' in page and "Märzen" not in page
    assert 'hx-get="/protokoll/tabelle?sort=recipe&amp;dir=desc"' in page

    # An explicitly empty search clears the filter again.
    cleared = client.get("/protokoll/tabelle", params={"q": ""}).text
    assert "Märzen" in cleared and "Citra" in cleared


def test_search_without_hits_shows_message(client, log_id):
    assert "Keine Sude gefunden" in client.get("/protokoll/tabelle", params={"q": "zzz"}).text
