from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.auth import hash_pin, verify_pin, check_rate_limit, record_failed_attempt, reset_rate_limit
from app.db import get_db
from app.models import User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(request, "login.html", {
        "error": request.session.pop("login_error", None),
    })


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    pin: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(name=username).first()

    if not user:
        request.session["login_error"] = "Invalid username or PIN."
        return RedirectResponse("/login", status_code=303)

    is_limited, seconds_left = check_rate_limit(user.id)
    if is_limited:
        mins = int(seconds_left // 60) + 1
        request.session["login_error"] = f"Account locked. Try again in {mins} minute(s)."
        return RedirectResponse("/login", status_code=303)

    if not verify_pin(user.pin_hash, pin):
        locked = record_failed_attempt(user.id)
        if locked:
            request.session["login_error"] = "Too many failed attempts. Account locked for 5 minutes."
        else:
            request.session["login_error"] = "Invalid username or PIN."
        return RedirectResponse("/login", status_code=303)

    reset_rate_limit(user.id)
    request.session["user_id"] = user.id
    return RedirectResponse("/", status_code=303)


@router.post("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)
