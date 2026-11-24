"""Jinja2 environment shared by all routers."""
from pathlib import Path

from fastapi.templating import Jinja2Templates

from app.formatting import de_date, de_decimal

BASE_DIR = Path(__file__).resolve().parent

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["de"] = de_decimal
templates.env.filters["de_date"] = de_date
