"""Fetch and cache daily prices via yfinance."""
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal

import yfinance as yf
from sqlalchemy.orm import Session

from app.models import Holding, PriceSnapshot

# Refresh prices that are older than this
_STALE_HOURS = 24


def _is_stale(holding: Holding) -> bool:
    """True if holding has no snapshots or latest fetch is older than 24 h."""
    if not holding.price_snapshots:
        return True
    latest = max(holding.price_snapshots, key=lambda s: s.fetched_at)
    age = datetime.now(timezone.utc) - latest.fetched_at.replace(tzinfo=timezone.utc)
    return age > timedelta(hours=_STALE_HOURS)


def fetch_prices(holding: Holding, db: Session) -> list[PriceSnapshot]:
    """
    Pull up to 90 days of daily close prices from Yahoo Finance and upsert
    into price_snapshots. Returns the updated snapshot list.
    """
    try:
        tk = yf.Ticker(holding.ticker)
        hist = tk.history(period="3mo", auto_adjust=True)
        info = tk.fast_info
        currency = getattr(info, "currency", "USD") or "USD"
    except Exception:
        return holding.price_snapshots

    if hist.empty:
        return holding.price_snapshots

    now = datetime.now(timezone.utc)
    existing = {s.date: s for s in holding.price_snapshots}

    for ts, row in hist.iterrows():
        day = ts.date()
        price = Decimal(str(round(float(row["Close"]), 6)))
        if day in existing:
            existing[day].price = price
            existing[day].currency = currency
            existing[day].fetched_at = now
        else:
            snap = PriceSnapshot(
                holding_id=holding.id,
                date=day,
                price=price,
                currency=currency,
                fetched_at=now,
            )
            db.add(snap)
            existing[day] = snap

    db.flush()
    # Reload relationship
    db.refresh(holding)
    return holding.price_snapshots


def refresh_if_stale(holding: Holding, db: Session) -> list[PriceSnapshot]:
    if _is_stale(holding):
        return fetch_prices(holding, db)
    return holding.price_snapshots


def refresh_all(db: Session) -> dict[str, bool]:
    """Refresh all stale holdings. Returns {ticker: success}."""
    results = {}
    for holding in db.query(Holding).all():
        if _is_stale(holding):
            try:
                fetch_prices(holding, db)
                results[holding.ticker] = True
            except Exception:
                results[holding.ticker] = False
    db.commit()
    return results


def latest_snapshot(holding: Holding) -> PriceSnapshot | None:
    if not holding.price_snapshots:
        return None
    return max(holding.price_snapshots, key=lambda s: s.date)
