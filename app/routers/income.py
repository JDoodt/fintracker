from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Income, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _pop_flash(request: Request) -> dict | None:
    return request.session.pop("flash", None)


@router.get("/income", response_class=HTMLResponse)
async def income_list(
    request: Request,
    month: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from datetime import date
    today = date.today()
    if month is None:
        month = today.strftime("%Y-%m")

    records = db.query(Income).filter(Income.month == month).order_by(Income.id).all()
    total = sum(r.amount for r in records)

    return templates.TemplateResponse(request, "income.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "records": records,
        "filter_month": month,
        "total": total,
        "today_month": today.strftime("%Y-%m"),
    })


@router.post("/income")
async def income_create(
    request: Request,
    month: str = Form(...),
    amount: str = Form(...),
    label: str = Form(...),
    recurring: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    errors = []

    import re
    if not re.match(r"^\d{4}-\d{2}$", month):
        errors.append("Month must be YYYY-MM.")

    try:
        parsed_amount = Decimal(amount.replace(",", "."))
        if parsed_amount <= 0:
            errors.append("Amount must be positive.")
    except Exception:
        errors.append("Invalid amount.")
        parsed_amount = None

    if not label.strip():
        errors.append("Label is required.")

    if errors:
        from datetime import date
        today = date.today()
        records = db.query(Income).filter(Income.month == month).order_by(Income.id).all()
        total = sum(r.amount for r in records)
        return templates.TemplateResponse(request, "income.html", {
            "current_user": current_user,
            "flash": {"type": "danger", "message": " ".join(errors)},
            "records": records,
            "filter_month": month,
            "total": total,
            "today_month": today.strftime("%Y-%m"),
        }, status_code=422)

    existing = db.query(Income).filter_by(month=month, label=label.strip()).first()
    if existing:
        request.session["flash"] = {"type": "warning", "message": f"Income '{label}' for {month} already exists."}
        return RedirectResponse(f"/income?month={month}", status_code=303)

    record = Income(
        month=month,
        amount=parsed_amount,
        label=label.strip(),
        recurring=recurring == "on",
    )
    db.add(record)
    db.commit()

    request.session["flash"] = {"type": "success", "message": "Income entry added."}
    return RedirectResponse(f"/income?month={month}", status_code=303)


@router.post("/income/{income_id}/delete")
async def income_delete(
    income_id: int,
    request: Request,
    month: str = Form(default=""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    record = db.get(Income, income_id)
    if record:
        saved_month = record.month
        db.delete(record)
        db.commit()
        request.session["flash"] = {"type": "success", "message": "Income entry deleted."}
        return RedirectResponse(f"/income?month={saved_month}", status_code=303)
    return RedirectResponse("/income", status_code=303)
