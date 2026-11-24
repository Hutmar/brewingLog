"""Pages of the brewing log (Protokoll)."""
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.repositories import brewing_logs as repo
from app.services import brewing_log_form as form_service
from app.services import brewing_logs as service
from app.templating import templates

router = APIRouter(prefix="/protokoll")

SessionDep = Annotated[Session, Depends(get_session)]

MESSAGES = {"saved": "Sud gespeichert.", "deleted": "Sud gelöscht."}
REQUIRED_FIELDS = {f.name for f in form_service.NUMBER_FIELDS if f.required} | {
    "recipe_name",
    "brewing_date",
    "yeast",
}


async def form_data(request: Request) -> dict[str, str]:
    form = await request.form()
    return {key: str(value) for key, value in form.items()}


FormDep = Annotated[dict[str, str], Depends(form_data)]


def _form_page(
    request: Request,
    session: Session,
    raw: dict[str, str],
    errors: dict[str, str],
    brewing_log_id: int | None,
):
    context = {
        "values": raw,
        "errors": errors,
        "brewing_log_id": brewing_log_id,
        "yeasts": repo.list_yeasts(session),
        "recipe_names": repo.list_recipe_names(session),
        "required": REQUIRED_FIELDS,
    }
    return templates.TemplateResponse(request, "protokoll/form.html", context)


@router.get("", response_class=HTMLResponse)
def overview(
    request: Request, session: SessionDep, msg: str | None = None, error: str | None = None
):
    context = {
        "rows": service.build_overview(session),
        "message": MESSAGES.get(msg or ""),
        "error": error,
    }
    return templates.TemplateResponse(request, "protokoll/list.html", context)


@router.get("/neu", response_class=HTMLResponse)
def new_form(request: Request, session: SessionDep):
    return _form_page(request, session, form_service.blank_input(), {}, None)


@router.post("/berechnen", response_class=HTMLResponse)
def calculate(request: Request, raw: FormDep):
    calculated = form_service.live_calculation(raw)
    context = {"calculated": calculated, "hints": form_service.hints(calculated)}
    return templates.TemplateResponse(request, "protokoll/_calculated.html", context)


@router.post("", response_class=HTMLResponse)
def create(request: Request, session: SessionDep, raw: FormDep):
    log, errors = form_service.save(session, raw)
    if log is None:
        return _form_page(request, session, raw, errors, None)
    return RedirectResponse(f"/protokoll/{log.brewing_log_id}?msg=saved", status_code=303)


@router.get("/{brewing_log_id:int}", response_class=HTMLResponse)
def detail(request: Request, session: SessionDep, brewing_log_id: int, msg: str | None = None):
    result = service.build_detail(session, brewing_log_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Sud nicht gefunden")
    context = {"detail": result, "message": MESSAGES.get(msg or "")}
    return templates.TemplateResponse(request, "protokoll/detail.html", context)


@router.get("/{brewing_log_id:int}/bearbeiten", response_class=HTMLResponse)
def edit_form(request: Request, session: SessionDep, brewing_log_id: int):
    log = repo.get(session, brewing_log_id)
    if log is None:
        raise HTTPException(status_code=404, detail="Sud nicht gefunden")
    return _form_page(request, session, form_service.input_from_log(log), {}, brewing_log_id)


@router.post("/{brewing_log_id:int}", response_class=HTMLResponse)
def update(request: Request, session: SessionDep, brewing_log_id: int, raw: FormDep):
    log, errors = form_service.save(session, raw, brewing_log_id)
    if log is None:
        return _form_page(request, session, raw, errors, brewing_log_id)
    return RedirectResponse(f"/protokoll/{log.brewing_log_id}?msg=saved", status_code=303)


@router.post("/{brewing_log_id:int}/loeschen")
def delete(session: SessionDep, brewing_log_id: int):
    error = form_service.delete(session, brewing_log_id)
    params = {"error": error} if error else {"msg": "deleted"}
    return RedirectResponse(f"/protokoll?{urlencode(params)}", status_code=303)
