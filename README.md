# Brauprotokoll (Brewing Log)

A lean web application for documenting beer brewing sessions (brewing log) and managing the ingredients used.
Stack: Python, FastAPI, HTMX, Jinja2, SQLAlchemy, Alembic, PostgreSQL.
The user interface and the URLs (`/protokoll`, `/rohstoffe`) are in German.

## Requirements

- Python 3.12 or newer
- PostgreSQL (the primary target; the application only uses portable SQLAlchemy features)

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Create the database and user (example, adjust the password):

```sql
CREATE ROLE brauprotokoll LOGIN PASSWORD 'secret';
CREATE DATABASE brauprotokoll OWNER brauprotokoll ENCODING 'UTF8' TEMPLATE template0;
```

Configuration: copy `.env.example` to `.env` and adjust it. The values can alternatively be set as environment variables.

| Variable       | Meaning                                         | Example                                                                  |
|----------------|-------------------------------------------------|--------------------------------------------------------------------------|
| `DATABASE_URL` | SQLAlchemy URL of the database (required)       | `postgresql+psycopg://brauprotokoll:secret@127.0.0.1:5432/brauprotokoll` |
| `LOG_LEVEL`    | Log level (optional, defaults to `INFO`)        | `INFO`                                                                   |

Note: If PostgreSQL runs in WSL, `networkingMode=mirrored` in `%USERPROFILE%\.wslconfig` helps to reach it from Windows. Use `127.0.0.1` as host instead of `localhost` so that no IPv6 connection is attempted.

### Running on Debian 13 with system packages (without pip)

```bash
sudo apt install python3-fastapi uvicorn python3-jinja2 python3-multipart \
    python3-sqlalchemy python3-alembic python3-psycopg python3-pydantic-settings
# only for the tests:
sudo apt install python3-pytest python3-httpx python3-coverage
```

The `uvicorn` package provides `/usr/bin/uvicorn`; `python3-starlette` and `python3-pydantic` are installed as dependencies.

### Running as a systemd service (WSL Debian)

The unit file `brewinglog.service` starts the application automatically. systemd must be enabled in WSL (`/etc/wsl.conf` contains `[boot]` with `systemd=true`).

1. Clone the repository and create the configuration:

   ```bash
   mkdir -p ~/projects && cd ~/projects
   git clone https://github.com/<github-user>/brewingLog.git
   cd brewingLog
   cp .env.example .env
   nano .env      # set DATABASE_URL (host 127.0.0.1, password of the role brauprotokoll)
   ```

2. Adjust `brewinglog.service` if needed. It assumes the user `reini`, the directory `/home/reini/projects/brewingLog`, `/usr/bin/uvicorn` and port 8010 (port 8000 is used by another application). `--host 0.0.0.0` makes the application reachable from other devices in the network; use `127.0.0.1` if only local access is wanted, because the application has no login.

3. Install and start the service:

   ```bash
   sudo cp brewinglog.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now brewinglog
   ```

4. Check the service:

   ```bash
   systemctl status brewinglog
   journalctl -u brewinglog -f
   ```

The application is then available at `http://<host>:8010/`. The database migrations run automatically on every start. If the database is not reachable or a migration fails, the service logs the error and is restarted every 5 seconds until the problem is fixed.

Update after changes in the repository:

```bash
cd ~/projects/brewingLog && git pull
sudo systemctl restart brewinglog
```

Other useful commands: `sudo systemctl stop brewinglog`, `sudo systemctl disable brewinglog` (no start at boot).

## Start

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The application is then available at <http://127.0.0.1:8000/>. Add `--reload` during development.

On startup the application checks for pending database migrations and runs them automatically. If a migration fails, startup is aborted with an error message. Existing data is never deleted and the schema is never recreated.

The application has no user management and no login. It is intended for personal use in a private network and should not be exposed to the internet unprotected.

## Tests

```powershell
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
.\.venv\Scripts\python -m pytest
```

The database-dependent tests run once with SQLite and once with PostgreSQL (in a temporary schema of the configured database, which is dropped afterwards). If PostgreSQL is not reachable, the PostgreSQL runs are skipped.

Test coverage: `python -m coverage run --source=app -m pytest`, then `python -m coverage report`.

## Structure

```
app/
  main.py            Entry point, startup migration, error pages
  config.py          Settings from environment variables
  db.py              Engine and sessions
  models.py          SQLAlchemy models (names as in brauprotokoll.sql)
  migrate.py         Automatic Alembic migration
  parsing.py         Number input with comma or dot
  formatting.py      Display formats (German date and decimal comma)
  repositories/      Database access
  services/          Business logic (calculations.py contains all calculations)
  routers/           Pages and HTMX fragments
  templates/         Jinja2 templates (no business logic, no database access)
  static/            htmx.min.js (local) and style.css
migrations/          Versioned Alembic migrations
tests/               Automated tests
```

## Features

**Brewing log** (`/protokoll`): overview of all brews (newest first), detail view with grouped data, create, edit and delete (with confirmation). Recipe names are suggested from previous brews, the yeast is chosen from the ingredients of type "Hefe" (yeast). Each brew has one rating (1–10) with a taste description.

**Calculations** (`app/services/calculations.py`, formulas taken from the former Excel sheet):

- Alcohol before secondary fermentation from the gravity after boiling and at bottling
- Dilution volume and bottling volume
- Alcohol after secondary fermentation (= target alcohol)
- Sugar per 0.5 l and 0.33 l bottle, total sugar
- Target pressure
- Duration of main fermentation, maturation and total duration (display only)

Calculated values are shown live in the form. If a field with a "Berechnet" (calculated) hint is left empty, the calculated value is stored; an entered value takes precedence. Sugar per bottle, target pressure and durations are not stored.

**Ingredients** (`/rohstoffe`): common management of all ingredient types (malt, hops, yeast or free input) with a filter by type, dynamic attributes (name, data type, value), stock in kg and change date. Suggestions for attribute names and data types come from existing ingredients of the same type. An ingredient that is used as yeast in a brew cannot be deleted.

Not part of the application: recipe management, fermentation tracking, water management, costs, statistics, multi-user operation, stock bookings, purchasing, Excel import (the legacy data is entered manually).

## Data model

`brauprotokoll.sql` is the binding basis; table and column names are used unchanged. Because the DDL defines plain `INTEGER PRIMARY KEY` columns without automatic ID generation, the first migration creates one sequence per table, which the application uses to assign IDs.
