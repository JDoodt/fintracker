from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from typing import Optional

from app.db import get_db
from app.deps import get_current_user, require_admin
from app.models import Category, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _pop_flash(request: Request) -> dict | None:
    return request.session.pop("flash", None)


def _build_tree(categories: list[Category]) -> list[dict]:
    by_id = {c.id: {"cat": c, "children": []} for c in categories}
    roots = []
    for c in categories:
        if c.parent_id is None:
            roots.append(by_id[c.id])
        elif c.parent_id in by_id:
            by_id[c.parent_id]["children"].append(by_id[c.id])
    return roots


@router.get("/categories", response_class=HTMLResponse)
async def categories_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cats = db.query(Category).order_by(Category.parent_id.nulls_first(), Category.name).all()
    top_level = [c for c in cats if c.parent_id is None and not c.archived]
    return templates.TemplateResponse(request, "categories.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "tree": _build_tree(cats),
        "top_level": top_level,
    })


@router.post("/categories")
async def category_create(
    request: Request,
    name: str = Form(...),
    parent_id: Optional[str] = Form(None),
    color: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    pid = int(parent_id) if parent_id and parent_id.strip() else None
    cat = Category(name=name.strip(), parent_id=pid, color=color or None)
    db.add(cat)
    db.commit()
    request.session["flash"] = {"type": "success", "message": f"Category '{name}' created."}
    return RedirectResponse("/categories", status_code=303)


@router.post("/categories/{cat_id}/archive")
async def category_archive(
    cat_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    cat = db.get(Category, cat_id)
    if cat:
        cat.archived = not cat.archived
        db.commit()
    return RedirectResponse("/categories", status_code=303)


@router.get("/admin/users", response_class=HTMLResponse)
async def users_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    users = db.query(User).order_by(User.name).all()
    return templates.TemplateResponse(request, "admin_users.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "users": users,
    })


@router.post("/admin/users")
async def user_create(
    request: Request,
    name: str = Form(...),
    pin: str = Form(...),
    is_admin: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from app.auth import hash_pin
    from app.models import User as UserModel
    from datetime import datetime, timezone

    errors = []
    if not pin.isdigit() or not (4 <= len(pin) <= 8):
        errors.append("PIN must be 4–8 digits.")
    if db.query(UserModel).filter_by(name=name.strip()).first():
        errors.append(f"Username '{name}' already taken.")

    if errors:
        users = db.query(UserModel).order_by(UserModel.name).all()
        return templates.TemplateResponse(request, "admin_users.html", {
            "current_user": current_user,
            "flash": {"type": "danger", "message": " ".join(errors)},
            "users": users,
        }, status_code=422)

    user = UserModel(
        name=name.strip(),
        pin_hash=hash_pin(pin),
        created_at=datetime.now(timezone.utc),
        is_admin=is_admin == "on",
    )
    db.add(user)
    db.commit()
    request.session["flash"] = {"type": "success", "message": f"User '{name}' created."}
    return RedirectResponse("/admin/users", status_code=303)


@router.post("/admin/users/{user_id}/reset-pin")
async def user_reset_pin(
    user_id: int,
    request: Request,
    pin: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from app.auth import hash_pin

    user = db.get(User, user_id)
    if not user:
        request.session["flash"] = {"type": "danger", "message": "User not found."}
        return RedirectResponse("/admin/users", status_code=303)

    if not pin.isdigit() or not (4 <= len(pin) <= 8):
        request.session["flash"] = {"type": "danger", "message": "PIN must be 4–8 digits."}
        return RedirectResponse("/admin/users", status_code=303)

    user.pin_hash = hash_pin(pin)
    db.commit()
    request.session["flash"] = {"type": "success", "message": f"PIN reset for '{user.name}'."}
    return RedirectResponse("/admin/users", status_code=303)
