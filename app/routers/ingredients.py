"""Pages and HTMX fragments of the ingredient management."""
from typing import Annotated
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.db import get_session
from app.repositories import ingredients as repo
from app.services import ingredients as service
from app.services.ingredients import AttributeInput, IngredientInput
from app.templating import templates

router = APIRouter(prefix="/rohstoffe")

SessionDep = Annotated[Session, Depends(get_session)]

MESSAGES = {
    "saved": "Rohstoff gespeichert.",
    "deleted": "Rohstoff gelöscht.",
    "stock": "Bestand gespeichert.",
}


def _redirect(art: str | None, msg: str | None = None, error: str | None = None):
    params = {k: v for k, v in {"art": art, "msg": msg, "error": error}.items() if v}
    url = "/rohstoffe" + (f"?{urlencode(params)}" if params else "")
    return RedirectResponse(url, status_code=303)


def _suggestions(session: Session, ingredient_type: str | None) -> dict:
    return {
        "type_suggestions": service.type_suggestions(session),
        "name_suggestions": repo.attribute_names(session, ingredient_type),
        "unit_suggestions": service.unit_suggestions(session),
    }


def _form_page(
    request: Request,
    session: Session,
    data: IngredientInput,
    errors: dict[str, str],
    ingredient_id: int | None,
):
    context = {
        "data": data,
        "errors": errors,
        "ingredient_id": ingredient_id,
        **_suggestions(session, data.ingredient_type.strip() or None),
    }
    return templates.TemplateResponse(request, "rohstoffe/form.html", context)


@router.get("", response_class=HTMLResponse)
def overview(
    request: Request,
    session: SessionDep,
    art: str | None = None,
    msg: str | None = None,
    error: str | None = None,
):
    context = {
        "overview": service.build_overview(session, art or None),
        "message": MESSAGES.get(msg or ""),
        "error": error,
    }
    return templates.TemplateResponse(request, "rohstoffe/list.html", context)


@router.get("/neu", response_class=HTMLResponse)
def new_form(request: Request, session: SessionDep, art: str | None = None):
    data = IngredientInput(ingredient_type=art or "", attributes=[AttributeInput()])
    return _form_page(request, session, data, {}, None)


@router.get("/attribut-zeile", response_class=HTMLResponse)
def attribute_row(request: Request):
    return templates.TemplateResponse(request, "rohstoffe/_attribute_row.html", {"attr": AttributeInput()})


@router.get("/vorschlaege", response_class=HTMLResponse)
def suggestions(request: Request, session: SessionDep, ingredient_type: str = ""):
    context = _suggestions(session, ingredient_type.strip() or None)
    return templates.TemplateResponse(request, "rohstoffe/_suggestions.html", context)


@router.get("/{ingredient_id:int}/bearbeiten", response_class=HTMLResponse)
def edit_form(request: Request, session: SessionDep, ingredient_id: int):
    ingredient = repo.get(session, ingredient_id)
    if ingredient is None:
        raise HTTPException(status_code=404, detail="Rohstoff nicht gefunden")
    data = service.input_from_ingredient(ingredient)
    data.stock = data.stock.replace(".", ",")
    if not data.attributes:
        data.attributes.append(AttributeInput())
    return _form_page(request, session, data, {}, ingredient_id)


def _collect(
    ingredient_type: str,
    name: str,
    stock: str,
    unit: str,
    attr_name: list[str],
    attr_value: list[str],
) -> IngredientInput:
    attributes = [AttributeInput(n, v) for n, v in zip(attr_name, attr_value, strict=False)]
    return IngredientInput(ingredient_type, name, stock, unit, attributes)


@router.post("", response_class=HTMLResponse)
def create(
    request: Request,
    session: SessionDep,
    ingredient_type: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "",
    stock: Annotated[str, Form()] = "",
    unit: Annotated[str, Form()] = "",
    attr_name: Annotated[list[str], Form()] = [],
    attr_value: Annotated[list[str], Form()] = [],
):
    data = _collect(ingredient_type, name, stock, unit, attr_name, attr_value)
    ingredient, errors = service.save_ingredient(session, data)
    if ingredient is None:
        if not data.attributes:
            data.attributes.append(AttributeInput())
        return _form_page(request, session, data, errors, None)
    return _redirect(ingredient.ingredient_type, msg="saved")


@router.post("/{ingredient_id:int}", response_class=HTMLResponse)
def update(
    request: Request,
    session: SessionDep,
    ingredient_id: int,
    ingredient_type: Annotated[str, Form()] = "",
    name: Annotated[str, Form()] = "",
    stock: Annotated[str, Form()] = "",
    unit: Annotated[str, Form()] = "",
    attr_name: Annotated[list[str], Form()] = [],
    attr_value: Annotated[list[str], Form()] = [],
):
    data = _collect(ingredient_type, name, stock, unit, attr_name, attr_value)
    ingredient, errors = service.save_ingredient(session, data, ingredient_id)
    if ingredient is None:
        if not data.attributes:
            data.attributes.append(AttributeInput())
        return _form_page(request, session, data, errors, ingredient_id)
    return _redirect(ingredient.ingredient_type, msg="saved")


@router.post("/{ingredient_id:int}/bestand")
def change_stock(
    session: SessionDep,
    ingredient_id: int,
    stock: Annotated[str, Form()] = "",
    art: Annotated[str, Form()] = "",
):
    error = service.update_stock(session, ingredient_id, stock)
    return _redirect(art or None, msg=None if error else "stock", error=error)


@router.post("/{ingredient_id:int}/loeschen")
def delete(
    session: SessionDep,
    ingredient_id: int,
    art: Annotated[str, Form()] = "",
):
    error = service.delete_ingredient(session, ingredient_id)
    return _redirect(art or None, msg=None if error else "deleted", error=error)
