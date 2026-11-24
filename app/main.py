"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import get_settings
from app.migrate import run_migrations
from app.routers import brewing_logs, ingredients
from app.templating import BASE_DIR, templates

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logging.basicConfig(level=get_settings().log_level)
    run_migrations()
    yield


app = FastAPI(title="Brauprotokoll", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(brewing_logs.router)
app.include_router(ingredients.router)


@app.get("/", include_in_schema=False)
def index() -> RedirectResponse:
    return RedirectResponse("/protokoll")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _error_page(request: Request, status_code: int, heading: str, text: str):
    return templates.TemplateResponse(
        request, "error.html", {"heading": heading, "text": text}, status_code=status_code
    )


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404:
        return _error_page(request, 404, "Seite nicht gefunden", "Der gesuchte Eintrag existiert nicht (mehr).")
    return _error_page(request, exc.status_code, "Fehler", str(exc.detail))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    logger.exception("Unhandled error for %s %s", request.method, request.url.path)
    return _error_page(
        request, 500, "Unerwarteter Fehler", "Es ist ein Fehler aufgetreten. Es wurden keine unvollständigen Daten gespeichert."
    )
