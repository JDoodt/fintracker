import csv
import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Category, Expense, Income, User

router = APIRouter(prefix="/api/export", tags=["exports"])

_CSV_FIELDS = ["type", "date", "amount", "category", "description", "label", "user", "recurring", "source"]


def _parse_date(s: Optional[str], fallback: date) -> date:
    try:
        return date.fromisoformat(s)
    except (TypeError, ValueError):
        return fallback


def _income_months(from_date: date, to_date: date) -> list[str]:
    """Return YYYY-MM strings covering the range [from_date, to_date]."""
    months = []
    y, m = from_date.year, from_date.month
    while (y, m) <= (to_date.year, to_date.month):
        months.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return months


def _query_expenses(db: Session, from_date: date, to_date: date) -> list[Expense]:
    return (
        db.query(Expense)
        .filter(Expense.date >= from_date, Expense.date <= to_date)
        .order_by(Expense.date, Expense.id)
        .all()
    )


def _query_income(db: Session, from_date: date, to_date: date) -> list[Income]:
    months = _income_months(from_date, to_date)
    if not months:
        return []
    return db.query(Income).filter(Income.month.in_(months)).order_by(Income.month, Income.id).all()


def _query_categories(db: Session) -> list[Category]:
    return db.query(Category).order_by(Category.id).all()


@router.get("/csv")
def export_csv(
    request: Request,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    fd = _parse_date(from_date, date(today.year, today.month, 1))
    td = _parse_date(to_date, today)

    expenses = _query_expenses(db, fd, td)
    income_records = _query_income(db, fd, td)

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=_CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()

    for e in expenses:
        writer.writerow({
            "type": "expense",
            "date": e.date.isoformat(),
            "amount": str(e.amount),
            "category": e.category.name if e.category else "",
            "description": e.description or "",
            "label": "",
            "user": e.user.name,
            "recurring": "yes" if e.recurring else "no",
            "source": e.source,
        })

    for r in income_records:
        writer.writerow({
            "type": "income",
            "date": r.month,
            "amount": str(r.amount),
            "category": "",
            "description": "",
            "label": r.label,
            "user": "",
            "recurring": "yes" if r.recurring else "no",
            "source": "",
        })

    filename = f"fintracker_{fd}_{td}.csv"
    content = buf.getvalue().encode("utf-8-sig")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv; charset=utf-8-sig",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/json")
def export_json(
    request: Request,
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    today = date.today()
    fd = _parse_date(from_date, date(today.year, today.month, 1))
    td = _parse_date(to_date, today)

    expenses = _query_expenses(db, fd, td)
    income_records = _query_income(db, fd, td)
    categories = _query_categories(db)

    payload = {
        "exported_at": datetime.utcnow().isoformat() + "Z",
        "from": fd.isoformat(),
        "to": td.isoformat(),
        "expenses": [
            {
                "id": e.id,
                "date": e.date.isoformat(),
                "amount": float(e.amount),
                "category_id": e.category_id,
                "category": e.category.name if e.category else None,
                "description": e.description,
                "recurring": e.recurring,
                "source": e.source,
                "user": e.user.name,
            }
            for e in expenses
        ],
        "income": [
            {
                "id": r.id,
                "month": r.month,
                "amount": float(r.amount),
                "label": r.label,
                "recurring": r.recurring,
            }
            for r in income_records
        ],
        "categories": [
            {
                "id": c.id,
                "name": c.name,
                "parent_id": c.parent_id,
                "color": c.color,
                "archived": c.archived,
            }
            for c in categories
        ],
    }

    filename = f"fintracker_{fd}_{td}.json"
    content = json.dumps(payload, indent=2, ensure_ascii=False).encode("utf-8")

    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
