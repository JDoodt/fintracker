from datetime import date
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.db import get_db
from app.models import Category, Expense, Income

router = APIRouter(prefix="/api/reports", tags=["reports"])


def _f(value) -> float:
    """Safely convert Decimal/None to float."""
    return float(value) if value is not None else 0.0


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return start, end


def _build_monthly(year: int, month: int, db: Session) -> dict:
    month_str = f"{year:04d}-{month:02d}"
    start, end = _month_bounds(year, month)

    income_total = db.query(func.sum(Income.amount)).filter(Income.month == month_str).scalar()

    total_spend = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start, Expense.date < end
    ).scalar()

    recurring_spend = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start, Expense.date < end, Expense.recurring.is_(True)
    ).scalar()

    cat_rows = (
        db.query(Category.id, Category.name, func.sum(Expense.amount).label("total"))
        .join(Expense, Expense.category_id == Category.id)
        .filter(Expense.date >= start, Expense.date < end)
        .group_by(Category.id, Category.name)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )
    by_category = [
        {"category_id": r[0], "category_name": r[1], "total": _f(r[2])}
        for r in cat_rows
    ]
    uncategorized = db.query(func.sum(Expense.amount)).filter(
        Expense.date >= start, Expense.date < end, Expense.category_id.is_(None)
    ).scalar()
    if uncategorized:
        by_category.append({"category_id": None, "category_name": "Uncategorized", "total": _f(uncategorized)})

    top10 = (
        db.query(Expense)
        .filter(Expense.date >= start, Expense.date < end)
        .order_by(Expense.amount.desc())
        .limit(10)
        .all()
    )

    income_f = _f(income_total)
    spend_f = _f(total_spend)
    pct = round(spend_f / income_f * 100, 1) if income_f else None

    return {
        "year": year,
        "month": month,
        "income": income_f,
        "total_spend": spend_f,
        "net": round(income_f - spend_f, 2),
        "pct_spent": pct,
        "by_category": by_category,
        "recurring_spend": _f(recurring_spend),
        "top10": [
            {
                "date": e.date.isoformat(),
                "amount": _f(e.amount),
                "description": e.description,
                "category_name": e.category.name if e.category else None,
            }
            for e in top10
        ],
    }


@router.get("/monthly")
def monthly_report(
    year: int = Query(...),
    month: int = Query(..., ge=1, le=12),
    db: Session = Depends(get_db),
):
    return _build_monthly(year, month, db)


@router.get("/yearly")
def yearly_report(year: int = Query(...), db: Session = Depends(get_db)):
    months = [_build_monthly(year, m, db) for m in range(1, 13)]
    return {
        "year": year,
        "months": months,
        "total_income": round(sum(m["income"] for m in months), 2),
        "total_spend": round(sum(m["total_spend"] for m in months), 2),
    }


@router.get("/trend")
def trend_report(months: int = Query(default=12, ge=1, le=36), db: Session = Depends(get_db)):
    today = date.today()
    base = today.year * 12 + (today.month - 1)

    points = []
    for i in range(months - 1, -1, -1):
        idx = base - i
        y, m = divmod(idx, 12)
        m += 1
        month_str = f"{y:04d}-{m:02d}"
        start, end = _month_bounds(y, m)

        income = db.query(func.sum(Income.amount)).filter(Income.month == month_str).scalar()
        spend = db.query(func.sum(Expense.amount)).filter(
            Expense.date >= start, Expense.date < end
        ).scalar()

        points.append({"month": month_str, "total_spend": _f(spend), "income": _f(income)})

    return {"points": points}
