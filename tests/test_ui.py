from app.db import get_session
from app.main import app


def test_navigation_marks_active_section(client):
    protokoll = client.get("/protokoll").text
    assert 'href="/protokoll" class="active"' in protokoll
    assert 'href="/rohstoffe" class="active"' not in protokoll
    assert 'href="/rohstoffe" class="active"' in client.get("/rohstoffe").text


def test_unknown_page_shows_friendly_404(client):
    response = client.get("/gibt-es-nicht")
    assert response.status_code == 404
    assert "Seite nicht gefunden" in response.text and "<nav" in response.text


def test_unexpected_error_shows_500_page(client):
    def broken():
        raise RuntimeError("database down")
        yield

    app.dependency_overrides[get_session] = broken
    response = client.get("/protokoll")
    assert response.status_code == 500
    assert "Unerwarteter Fehler" in response.text
    assert "database down" not in response.text


def test_htmx_swaps_error_responses(client):
    assert '"code":"[45]..","swap":true' in client.get("/protokoll").text


def test_menu_lists_ingredients_before_protokoll(client):
    page = client.get("/rohstoffe").text
    assert page.index('href="/rohstoffe"') < page.index('href="/protokoll"')


def test_favicon_is_linked_and_served(client):
    page = client.get("/rohstoffe").text
    assert 'rel="icon" type="image/svg+xml" href="/static/favicon.svg"' in page
    response = client.get("/static/favicon.svg")
    assert response.status_code == 200 and "<svg" in response.text
