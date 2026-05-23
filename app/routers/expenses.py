from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Category, Expense, User

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _flat_categories(db: Session) -> list[Category]:
    return db.query(Category).filter_by(archived=False).order_by(Category.name).all()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    today = date.today()
    return templates.TemplateResponse(request, "dashboard.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "current_month": today.strftime("%Y-%m"),
        "current_year": today.year,
    })


@router.get("/expenses", response_class=HTMLResponse)
async def expenses_list(
    request: Request,
    month: Optional[str] = None,
    category_id: Optional[int] = None,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    if month is None:
        month = today.strftime("%Y-%m")

    query = db.query(Expense)
    if month:
        try:
            y, m = month.split("-")
            query = query.filter(
                Expense.date >= date(int(y), int(m), 1),
                Expense.date < _next_month(int(y), int(m)),
            )
        except (ValueError, AttributeError):
            pass
    if category_id:
        query = query.filter(Expense.category_id == category_id)
    if user_id:
        query = query.filter(Expense.user_id == user_id)

    expenses = query.order_by(Expense.date.desc(), Expense.id.desc()).all()
    categories = _flat_categories(db)
    users = db.query(User).order_by(User.name).all()

    total = sum(e.amount for e in expenses)

    return templates.TemplateResponse(request, "expenses_list.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "expenses": expenses,
        "categories": categories,
        "users": users,
        "filter_month": month,
        "filter_category_id": category_id,
        "filter_user_id": user_id,
        "total": total,
    })


@router.get("/expenses/new", response_class=HTMLResponse)
async def expense_new(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    categories = _flat_categories(db)
    return templates.TemplateResponse(request, "expenses_new.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "categories": categories,
        "today": date.today().isoformat(),
    })


@router.post("/expenses")
async def expense_create(
    request: Request,
    exp_date: str = Form(..., alias="date"),
    amount: str = Form(...),
    category_id: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    recurring: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    errors = []
    try:
        parsed_date = date.fromisoformat(exp_date)
    except ValueError:
        errors.append("Invalid date.")
        parsed_date = None

    try:
        parsed_amount = Decimal(amount.replace(",", "."))
        if parsed_amount <= 0:
            errors.append("Amount must be positive.")
    except Exception:
        errors.append("Invalid amount.")
        parsed_amount = None

    cat_id = int(category_id) if category_id and category_id.strip() else None

    if errors:
        categories = _flat_categories(db)
        return templates.TemplateResponse(request, "expenses_new.html", {
            "current_user": current_user,
            "flash": {"type": "danger", "message": " ".join(errors)},
            "categories": categories,
            "today": exp_date,
        }, status_code=422)

    expense = Expense(
        user_id=current_user.id,
        date=parsed_date,
        amount=parsed_amount,
        category_id=cat_id,
        description=description or None,
        recurring=recurring == "on",
        source="manual",
        created_at=datetime.now(timezone.utc),
    )
    db.add(expense)
    db.commit()

    request.session["flash"] = {"type": "success", "message": "Expense added."}
    return RedirectResponse("/expenses", status_code=303)


@router.post("/expenses/{expense_id}/delete")
async def expense_delete(
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    expense = db.get(Expense, expense_id)
    if expense and (expense.user_id == current_user.id or current_user.is_admin):
        db.delete(expense)
        db.commit()
        request.session["flash"] = {"type": "success", "message": "Expense deleted."}
    return RedirectResponse("/expenses", status_code=303)


def _next_month(year: int, month: int) -> date:
    if month == 12:
        return date(year + 1, 1, 1)
    return date(year, month + 1, 1)


def _pop_flash(request: Request) -> dict | None:
    return request.session.pop("flash", None)
