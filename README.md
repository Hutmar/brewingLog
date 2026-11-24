# Brauprotokoll

Schlanke Webanwendung zur Dokumentation von Bierbrauvorgängen (Protokoll) und zur Verwaltung der Rohstoffe.
Technik: Python, FastAPI, HTMX, Jinja2, SQLAlchemy, Alembic, PostgreSQL.

## Voraussetzungen

- Python 3.12 oder neuer
- PostgreSQL (primär vorgesehen; die Anwendung nutzt nur portable SQLAlchemy-Funktionen)

## Einrichtung

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Datenbank und Benutzer anlegen (Beispiel, Passwort anpassen):

```sql
CREATE ROLE brauprotokoll LOGIN PASSWORD 'geheim';
CREATE DATABASE brauprotokoll OWNER brauprotokoll ENCODING 'UTF8' TEMPLATE template0;
```

Konfiguration: `.env.example` nach `.env` kopieren und anpassen. Die Werte können alternativ als Umgebungsvariablen gesetzt werden.

| Variable       | Bedeutung                                                      | Beispiel                                                          |
|----------------|----------------------------------------------------------------|-------------------------------------------------------------------|
| `DATABASE_URL` | SQLAlchemy-URL der Datenbank (Pflicht)                         | `postgresql+psycopg://brauprotokoll:geheim@127.0.0.1:5432/brauprotokoll` |
| `LOG_LEVEL`    | Log-Stufe (optional, Standard `INFO`)                          | `INFO`                                                            |

Hinweis: Läuft PostgreSQL unter WSL, ist für den Zugriff von Windows aus `networkingMode=mirrored` in `%USERPROFILE%\.wslconfig` hilfreich. Als Host `127.0.0.1` statt `localhost` verwenden, damit keine IPv6-Verbindung versucht wird.

### Betrieb unter Debian 13 mit Systempaketen (ohne pip)

```bash
sudo apt install python3-fastapi uvicorn python3-jinja2 python3-multipart \
    python3-sqlalchemy python3-alembic python3-psycopg python3-pydantic-settings
# nur für die Tests:
sudo apt install python3-pytest python3-httpx python3-coverage
```

`uvicorn` stellt `/usr/bin/uvicorn` bereit, `python3-starlette` und `python3-pydantic` kommen als Abhängigkeiten mit. Als systemd-Dienst siehe `brewinglog.service`.

## Start

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Danach ist die Anwendung unter <http://127.0.0.1:8000/> erreichbar. Für die Entwicklung kann `--reload` ergänzt werden.

Beim Start prüft die Anwendung, ob Datenbankmigrationen ausstehen, und führt sie automatisch aus. Schlägt eine Migration fehl, bricht der Start mit einer Fehlermeldung ab. Bestehende Daten werden nicht gelöscht, das Schema wird nicht neu erstellt.

Die Anwendung hat keine Benutzerverwaltung und keine Anmeldung; sie ist für den persönlichen Einsatz im eigenen Netz gedacht und sollte nicht ungeschützt im Internet betrieben werden.

## Tests

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

Die datenbankabhängigen Tests laufen einmal mit SQLite und einmal mit PostgreSQL (in einem temporären Schema der konfigurierten Datenbank, das danach gelöscht wird). Ist PostgreSQL nicht erreichbar, werden die PostgreSQL-Läufe übersprungen.

Testabdeckung: `python -m coverage run --source=app -m pytest` und anschließend `python -m coverage report`.

## Aufbau

```
app/
  main.py            Einstiegspunkt, Start-Migration, Fehlerseiten
  config.py          Einstellungen aus Umgebungsvariablen
  db.py              Engine und Sessions
  models.py          SQLAlchemy-Modelle (Namen wie in brauprotokoll.sql)
  migrate.py         Automatische Alembic-Migration
  parsing.py         Zahleneingaben mit Komma oder Punkt
  formatting.py      Anzeigeformate (deutsches Datum und Dezimalkomma)
  repositories/      Datenbankzugriff
  services/          Fachlogik (calculations.py enthält alle Berechnungen)
  routers/           Seiten und HTMX-Fragmente
  templates/         Jinja2-Templates (ohne Fachlogik, ohne Datenbankzugriff)
  static/            htmx.min.js (lokal) und style.css
migrations/          Versionierte Alembic-Migrationen
tests/               Automatische Tests
```

## Funktionsumfang

**Protokoll** (`/protokoll`): Übersicht der Sude (nach Braudatum absteigend), Detailansicht mit gruppierten Daten, Anlegen, Bearbeiten und Löschen (mit Bestätigung). Rezeptnamen werden aus bisherigen Suden vorgeschlagen, die Hefe wird aus den Rohstoffen der Art „Hefe“ gewählt. Je Sud gibt es eine Bewertung (1–10) mit Geschmacksbeschreibung.

**Berechnungen** (`app/services/calculations.py`, Formeln aus der früheren Excel-Datei):

- Alkoholgehalt vor Nachgärung aus Stammwürze nach Kochen und bei Abfüllung
- Verdünnungsmenge, Abfüllmenge
- Alkoholgehalt nach Nachgärung (= Soll-Alkohol)
- Zucker pro 0,5-l- und 0,33-l-Flasche, Zucker gesamt
- Zieldruck
- Dauer Hauptgärung, Reifungsdauer und Gesamtdauer (nur Anzeige)

Berechnete Werte werden im Formular live angezeigt. Bleibt ein Feld mit „Berechnet“-Hinweis leer, wird der berechnete Wert gespeichert; ein eingegebener Wert hat Vorrang. Zucker pro Flasche, Zieldruck und Dauern werden nicht gespeichert.

**Rohstoffe** (`/rohstoffe`): gemeinsame Verwaltung aller Rohstoffarten (Malz, Hopfen, Hefe oder frei eingegeben) mit Filter nach Art, dynamischen Eigenschaften (Name, Datentyp, Wert), Bestand in kg und Änderungsdatum. Vorschläge für Eigenschaftsnamen und Datentypen stammen aus bestehenden Rohstoffen derselben Art. Ein Rohstoff, der in einem Sud als Hefe verwendet wird, kann nicht gelöscht werden.

Nicht Teil der Anwendung: Rezeptverwaltung, Gärverlauf, Wasserverwaltung, Kosten, Statistiken, Mehrbenutzerbetrieb, Lagerbuchungen, Einkauf, Excel-Import (die Altdaten werden manuell erfasst).

## Datenmodell

`brauprotokoll.sql` ist die verbindliche Grundlage; Tabellen- und Spaltennamen sind unverändert übernommen. Da die DDL reine `INTEGER PRIMARY KEY`-Spalten ohne automatische ID-Vergabe definiert, legt die erste Migration je Tabelle eine Sequence an, über die die Anwendung die IDs vergibt.
