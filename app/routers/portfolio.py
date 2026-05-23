from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

import yfinance as yf
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_user
from app.models import Holding, PriceSnapshot, User
from app.services.prices import latest_snapshot, refresh_if_stale

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


def _pop_flash(request: Request) -> dict | None:
    return request.session.pop("flash", None)


def _build_portfolio_view(holdings: list[Holding]) -> list[dict]:
    """Compute display data for each holding."""
    rows = []
    for h in holdings:
        snap = latest_snapshot(h)
        if snap is None:
            rows.append({
                "holding": h,
                "current_price": None,
                "current_value": None,
                "currency": "—",
                "change_1m_pct": None,
                "change_3m_pct": None,
                "history": [],
            })
            continue

        current_price = snap.price
        current_value = (h.quantity * current_price).quantize(Decimal("0.01"))
        currency = snap.currency

        snaps_sorted = sorted(h.price_snapshots, key=lambda s: s.date)

        def _pct_change(days: int) -> Optional[float]:
            from datetime import timedelta
            cutoff = snap.date - timedelta(days=days)
            candidates = [s for s in snaps_sorted if s.date <= cutoff]
            if not candidates:
                return None
            old_price = candidates[-1].price
            if old_price == 0:
                return None
            return float(((current_price - old_price) / old_price * 100).quantize(Decimal("0.01")))

        # History for chart: date + value (quantity × price)
        history = [
            {"date": s.date.isoformat(), "value": float((h.quantity * s.price).quantize(Decimal("0.01")))}
            for s in snaps_sorted
        ]

        rows.append({
            "holding": h,
            "current_price": float(current_price),
            "current_value": float(current_value),
            "currency": currency,
            "change_1m_pct": _pct_change(30),
            "change_3m_pct": _pct_change(90),
            "history": history,
        })
    return rows


@router.get("/portfolio", response_class=HTMLResponse)
async def portfolio_page(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    holdings = db.query(Holding).order_by(Holding.ticker).all()

    # Lazy refresh stale prices (silently skip failures)
    for h in holdings:
        try:
            refresh_if_stale(h, db)
        except Exception:
            pass
    db.commit()

    rows = _build_portfolio_view(holdings)

    total_value_eur = sum(
        r["current_value"] for r in rows if r["current_value"] is not None
    )

    return templates.TemplateResponse(request, "portfolio.html", {
        "current_user": current_user,
        "flash": _pop_flash(request),
        "rows": rows,
        "total_value": round(total_value_eur, 2),
    })


@router.post("/portfolio/holdings")
async def holding_add(
    request: Request,
    ticker: str = Form(...),
    quantity: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticker = ticker.strip().upper()
    errors = []

    try:
        qty = Decimal(quantity.replace(",", "."))
        if qty <= 0:
            errors.append("Menge muss positiv sein.")
    except Exception:
        errors.append("Ungültige Menge.")
        qty = None

    existing = db.query(Holding).filter_by(ticker=ticker).first()
    if existing:
        errors.append(f"Ticker {ticker} ist bereits vorhanden.")

    if not errors:
        # Validate ticker with Yahoo Finance and get display name
        try:
            info = yf.Ticker(ticker).fast_info
            name = getattr(yf.Ticker(ticker), "info", {}).get("longName") or ticker
        except Exception:
            name = ticker

        holding = Holding(
            ticker=ticker,
            name=name,
            quantity=qty,
            added_by=current_user.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(holding)
        db.flush()

        # Immediately fetch price history
        try:
            from app.services.prices import fetch_prices
            fetch_prices(holding, db)
        except Exception:
            pass

        db.commit()
        request.session["flash"] = {"type": "success", "message": f"{ticker} hinzugefügt."}
    else:
        request.session["flash"] = {"type": "danger", "message": " ".join(errors)}

    return RedirectResponse("/portfolio", status_code=303)


@router.post("/portfolio/holdings/{holding_id}/update")
async def holding_update(
    holding_id: int,
    request: Request,
    quantity: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    holding = db.get(Holding, holding_id)
    if not holding:
        return RedirectResponse("/portfolio", status_code=303)

    try:
        qty = Decimal(quantity.replace(",", "."))
        if qty > 0:
            holding.quantity = qty
            db.commit()
            request.session["flash"] = {"type": "success", "message": f"{holding.ticker} aktualisiert."}
    except Exception:
        request.session["flash"] = {"type": "danger", "message": "Ungültige Menge."}

    return RedirectResponse("/portfolio", status_code=303)


@router.post("/portfolio/holdings/{holding_id}/delete")
async def holding_delete(
    holding_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    holding = db.get(Holding, holding_id)
    if holding:
        db.delete(holding)
        db.commit()
        request.session["flash"] = {"type": "success", "message": f"{holding.ticker} entfernt."}
    return RedirectResponse("/portfolio", status_code=303)


@router.post("/portfolio/refresh")
async def portfolio_refresh(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.services.prices import fetch_prices
    holdings = db.query(Holding).all()
    for h in holdings:
        try:
            fetch_prices(h, db)
        except Exception:
            pass
    db.commit()
    request.session["flash"] = {"type": "success", "message": "Kurse aktualisiert."}
    return RedirectResponse("/portfolio", status_code=303)


@router.get("/api/portfolio/history")
def portfolio_history(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate portfolio value per day across all holdings."""
    holdings = db.query(Holding).all()
    if not holdings:
        return {"points": []}

    # Collect all dates
    from collections import defaultdict
    daily: dict[str, float] = defaultdict(float)

    for h in holdings:
        for snap in h.price_snapshots:
            key = snap.date.isoformat()
            daily[key] += float((h.quantity * snap.price).quantize(Decimal("0.01")))

    points = [{"date": d, "value": round(v, 2)} for d, v in sorted(daily.items())]
    return {"points": points}
