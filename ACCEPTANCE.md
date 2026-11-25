# Acceptance against the requirements

Status: implementation complete. "Test" means an automated test (SQLite and PostgreSQL). "Browser" means: only verified through server responses; the behaviour in the browser (HTMX interaction, smartphone layout) still has to be accepted manually.

The section numbers refer to `requirements.md` (in German).

| Section | Requirement | Status | Evidence / note |
|---------|-------------|--------|-----------------|
| 2 | Python, FastAPI, HTMX, Jinja2, PostgreSQL, SQLAlchemy, Alembic | met | `requirements.txt` |
| 2 | Data model as per DDL, no additional tables/columns | met with agreed changes | `app/models.py`, migrations `0001` and `0002`. One additional sequence per table for ID assignment (decision F1). `changes.md` (2026-11-24) requested schema changes, applied in `0002`: `ingredient.unit` added, `ingredient.stock` widened, `attribute_datatype` and `alcohol_current` removed, `pressure_current` widened to `numeric(3,2)`. |
| 2 | Low database dependency | met | Tests run with SQLite and PostgreSQL |
| 2, 7 | Automatic migration on startup, abort with a message on failure | met | `test_migrations.py`, `test_ingredient_edge_cases.py` |
| 2, 7 | Existing data is preserved, schema is not recreated | met | `test_migration_keeps_existing_data`. A database that was created manually from the DDL without an Alembic version would make startup abort with an error message (tables already exist); it is not overwritten. |
| 2 | Configuration through environment variables | met | `app/config.py`, `.env.example` |
| 3.1 | Browser operation, desktop and smartphone | browser | Responsive CSS, to be accepted manually |
| 3.1 | HTMX, little client-side JavaScript | met | HTMX only, one inline attribute to remove a row |
| 3.1 | No multi-user management | met | |
| 3.2 | Server-side validation, understandable errors, no data loss on form errors | met | `test_brewing_log_form.py`, `test_ingredients.py` |
| 3.2 | Decimal numbers independent of the locale | met | `test_parsing.py`, `test_robustness.py` |
| 4.1 | Overview by brewing date, recipe name, date, selected results, detail, new, edit, delete with confirmation | met | `test_brewing_logs.py`. Confirmation dialog: browser. |
| 4.2 | Recipe name as text with suggestions, reusable | met | `test_recipe_is_reused_and_rating_is_managed` |
| 4.3 | All log fields | met | Mapping to DDL columns as in `implementierungsplan.md` (F3–F5) |
| 4.3 | Sugar per bottle and target pressure display only | met | Not stored |
| 4.4 | Grouped detail view with editing | met | |
| 4.5 | Calculations central, traceable, overridable | met | `app/services/calculations.py`, reference values from Excel in `test_calculations.py` |
| 4.5 | Duration of main fermentation / maturation / total | met | Display only, not stored (as specified) |
| 4.6 | Data import from Excel | dropped | Done manually, at the client's request |
| 5.1–5.4 | Common ingredient management with filter, dropdown with free input, manual stock | met | `test_ingredients.py` |
| 5.3 | Dynamic attributes, attribute names from the data model/existing data | met with deviation | The DDL has no attribute catalog; suggestions come from existing ingredients of the same type (decision F9). Attribute values are free text (the data type column was removed on request). |
| 6 | Confirmation on delete, feedback, no inconsistent records | met | `test_robustness.py` (transactions, logging). Dialog: browser. |
| 8 | Separation of backend / data access / presentation | met | `routers`, `services`, `repositories`, `templates` |
| 8 | No database access and no business logic in templates | met | Templates only format; relations are loaded up front |
| 8 | Error handling and logging | met | Error pages 404/500, log entries |
| 8 | Automated tests | met | 212 tests, 97 % coverage of the application |
| 9 | Only brewing log and ingredient management | met | |

## To be checked manually (browser)

1. Create a new brew: live calculation while typing, "Berechnet" hints, saving with empty calculation fields.
2. Edit a brew and provoke an error (e.g. clear a required field): the input is preserved.
3. Delete a brew and an ingredient: the confirmation dialog appears.
4. Create an ingredient with attributes: add/remove rows, suggestions after changing the ingredient type.
5. Layout on a smartphone (navigation, tables, forms).
6. Brew overview: live search while typing, sorting by clicking "Status", "Rezept" and "Braudatum" (second click reverses), search/sort restored after reloading the page, status icons and end date.
7. Delete button only in the edit view, next to "Abbrechen", with confirmation.
8. Ingredient form: unit selection (`kg`, `g`, `pkg`, free input) and attributes without data type.
9. Favicon (stylized beer bottle) and menu order (Rohstoffe, then Protokoll).
