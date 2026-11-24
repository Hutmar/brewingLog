# Abnahme anhand der Anforderungen

Stand: Umsetzung abgeschlossen. „Test“ bedeutet automatisierter Test (SQLite und PostgreSQL). „Browser“ bedeutet: Nur über Server-Antworten geprüft, die Bedienung im Browser (HTMX-Interaktion, Smartphone-Darstellung) muss noch manuell abgenommen werden.

| Abschnitt | Anforderung | Status | Nachweis / Hinweis |
|-----------|-------------|--------|--------------------|
| 2 | Python, FastAPI, HTMX, Jinja2, PostgreSQL, SQLAlchemy, Alembic | erfüllt | `requirements.txt` |
| 2 | Datenmodell nach DDL, keine zusätzlichen Tabellen/Spalten | erfüllt | `app/models.py`, Migration `0001`. Zusätzlich je Tabelle eine Sequence für die ID-Vergabe (Entscheidung F1, keine neue Spalte). |
| 2 | Wenig Datenbankabhängigkeit | erfüllt | Tests laufen mit SQLite und PostgreSQL |
| 2, 7 | Automatische Migration beim Start, Abbruch mit Meldung bei Fehler | erfüllt | `test_migrations.py`, `test_ingredient_edge_cases.py` |
| 2, 7 | Bestehende Daten bleiben erhalten, Schema wird nicht neu erstellt | erfüllt | `test_migration_keeps_existing_data`. Eine bereits manuell per DDL angelegte Datenbank ohne Alembic-Version würde beim Start mit einer Fehlermeldung abbrechen (Tabellen existieren), nicht überschrieben. |
| 2 | Konfiguration über Umgebungsvariablen | erfüllt | `app/config.py`, `.env.example` |
| 3.1 | Bedienung per Browser, Desktop und Smartphone | Browser | Responsives CSS, noch manuell abzunehmen |
| 3.1 | HTMX, wenig clientseitiges JavaScript | erfüllt | Nur HTMX, ein Inline-Attribut zum Entfernen einer Zeile |
| 3.1 | Keine Mehrbenutzerverwaltung | erfüllt | |
| 3.2 | Serverseitige Validierung, verständliche Fehler, keine Datenverluste bei Formularfehlern | erfüllt | `test_brewing_log_form.py`, `test_ingredients.py` |
| 3.2 | Dezimalzahlen unabhängig von der Spracheinstellung | erfüllt | `test_parsing.py`, `test_robustness.py` |
| 4.1 | Übersicht nach Braudatum, Rezeptname, Datum, ausgewählte Ergebnisse, Detail, Neu, Bearbeiten, Löschen mit Abfrage | erfüllt | `test_brewing_logs.py`. Bestätigungsdialog: Browser. |
| 4.2 | Rezeptname als Text mit Vorschlägen, mehrfach verwendbar | erfüllt | `test_recipe_is_reused_and_rating_is_managed` |
| 4.3 | Alle Protokollfelder | erfüllt | Zuordnung zu DDL-Spalten wie in `implementierungsplan.md` (F3–F5) |
| 4.3 | Zucker je Gebinde und Zieldruck nur Anzeige | erfüllt | Nicht gespeichert |
| 4.4 | Gruppierte Detailansicht mit Bearbeitung | erfüllt | |
| 4.5 | Berechnungen zentral, nachvollziehbar, überschreibbar | erfüllt | `app/services/calculations.py`, Referenzwerte aus Excel in `test_calculations.py` |
| 4.5 | Dauer Hauptgärung/Reifung/gesamt | erfüllt | Anzeige, nicht gespeichert (Vorgabe) |
| 4.6 | Datenübernahme aus Excel | entfällt | Auf Wunsch des Auftraggebers manuell |
| 5.1–5.4 | Gemeinsame Rohstoffverwaltung mit Filter, Dropdown mit freier Eingabe, Bestand manuell | erfüllt | `test_ingredients.py` |
| 5.3 | Dynamische Attribute, Attributnamen aus Datenmodell/Bestand | erfüllt mit Abweichung | Die DDL enthält keinen Attributkatalog; Vorschläge kommen aus bestehenden Rohstoffen derselben Art (Entscheidung F9). Die Werteprüfung richtet sich nach dem Datentyp (`decimal`, `integer`, `date`, sonst Text). |
| 6 | Bestätigung beim Löschen, Rückmeldungen, keine inkonsistenten Datensätze | erfüllt | `test_robustness.py` (Transaktionen, Logging). Dialog: Browser. |
| 8 | Trennung Backend / Datenzugriff / Darstellung | erfüllt | `routers`, `services`, `repositories`, `templates` |
| 8 | Keine Datenbankzugriffe und keine Fachlogik in Templates | erfüllt | Templates formatieren nur; Beziehungen werden vorab geladen |
| 8 | Fehlerbehandlung und Protokollierung | erfüllt | Fehlerseiten 404/500, Logeinträge |
| 8 | Automatisierte Tests | erfüllt | 146 Tests, 96 % Abdeckung der Anwendung |
| 9 | Nur Protokoll und Rohstoffverwaltung | erfüllt | |

## Manuell zu prüfen (Browser)

1. Neuen Sud anlegen: Live-Berechnung beim Tippen, „Berechnet“-Hinweise, Speichern mit leeren Berechnungsfeldern.
2. Sud bearbeiten, Fehler provozieren (z. B. Pflichtfeld leeren): Eingaben bleiben erhalten.
3. Löschen von Sud und Rohstoff: Bestätigungsdialog erscheint.
4. Rohstoff mit Eigenschaften anlegen: Zeilen hinzufügen/entfernen, Vorschläge nach Wechsel der Rohstoffart.
5. Darstellung auf dem Smartphone (Navigation, Tabellen, Formulare).
