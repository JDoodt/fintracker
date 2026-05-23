from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from app.models import Category, Expense, Income
from tests.conftest import login


@pytest.fixture()
def month_data(db, admin_user, seeded_categories):
    """Insert a known set of expenses and income for 2026-05."""
    food_id = seeded_categories["food"].id
    essentials_id = seeded_categories["essentials"].id

    db.add(Income(month="2026-05", amount=Decimal("4000.00"), label="Salary", recurring=True))
    db.add(Income(month="2026-05", amount=Decimal("500.00"), label="Side gig", recurring=False))

    expenses = [
        Expense(user_id=admin_user.id, date=date(2026, 5, 1), amount=Decimal("800.00"),
                category_id=essentials_id, description="Rent", recurring=True,
                source="manual", created_at=datetime.now(timezone.utc)),
        Expense(user_id=admin_user.id, date=date(2026, 5, 5), amount=Decimal("120.50"),
                category_id=food_id, description="Supermarket",
                source="manual", created_at=datetime.now(timezone.utc)),
        Expense(user_id=admin_user.id, date=date(2026, 5, 10), amount=Decimal("45.00"),
                category_id=food_id, description="Restaurant",
                source="manual", created_at=datetime.now(timezone.utc)),
        Expense(user_id=admin_user.id, date=date(2026, 5, 15), amount=Decimal("30.00"),
                category_id=None, description="Cash",
                source="manual", created_at=datetime.now(timezone.utc)),
    ]
    for e in expenses:
        db.add(e)
    db.flush()
    return {
        "income": Decimal("4500.00"),
        "total_spend": Decimal("995.50"),
        "food_total": Decimal("165.50"),
        "essentials_total": Decimal("800.00"),
        "uncategorized": Decimal("30.00"),
        "recurring_spend": Decimal("800.00"),
    }


def test_monthly_report_totals(client, admin_user, month_data):
    login(client)
    resp = client.get("/api/reports/monthly?year=2026&month=5")
    assert resp.status_code == 200
    data = resp.json()

    assert data["income"] == pytest.approx(4500.00)
    assert data["total_spend"] == pytest.approx(995.50)
    assert data["net"] == pytest.approx(3504.50)
    assert data["pct_spent"] == pytest.approx(22.1)


def test_monthly_report_by_category(client, admin_user, month_data, seeded_categories):
    login(client)
    resp = client.get("/api/reports/monthly?year=2026&month=5")
    data = resp.json()

    names = {c["category_name"]: c["total"] for c in data["by_category"]}
    assert names["Essentials"] == pytest.approx(800.00)
    assert names["Food"] == pytest.approx(165.50)
    assert names["Uncategorized"] == pytest.approx(30.00)


def test_monthly_report_recurring_spend(client, admin_user, month_data):
    login(client)
    data = client.get("/api/reports/monthly?year=2026&month=5").json()
    assert data["recurring_spend"] == pytest.approx(800.00)


def test_monthly_report_top10(client, admin_user, month_data):
    login(client)
    data = client.get("/api/reports/monthly?year=2026&month=5").json()

    assert len(data["top10"]) == 4
    # Sorted descending by amount
    assert data["top10"][0]["amount"] == pytest.approx(800.00)
    assert data["top10"][0]["description"] == "Rent"


def test_monthly_report_empty_month(client, admin_user):
    """A month with no data returns zeros, not errors."""
    login(client)
    data = client.get("/api/reports/monthly?year=2020&month=1").json()
    assert data["income"] == 0.0
    assert data["total_spend"] == 0.0
    assert data["net"] == 0.0
    assert data["pct_spent"] is None
    assert data["by_category"] == []


def test_monthly_report_no_income_pct_is_none(client, admin_user, db):
    """pct_spent is None when income is zero."""
    login(client)
    db.add(Expense(
        user_id=admin_user.id, date=date(2024, 3, 1),
        amount=Decimal("50.00"), source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    data = client.get("/api/reports/monthly?year=2024&month=3").json()
    assert data["pct_spent"] is None


def test_trend_report_returns_n_points(client, admin_user):
    login(client)
    data = client.get("/api/reports/trend?months=6").json()
    assert len(data["points"]) == 6


def test_trend_report_months_are_in_order(client, admin_user):
    login(client)
    data = client.get("/api/reports/trend?months=12").json()
    months = [p["month"] for p in data["points"]]
    assert months == sorted(months)


def test_trend_report_contains_data(client, admin_user, month_data):
    login(client)
    data = client.get("/api/reports/trend?months=12").json()
    may = next(p for p in data["points"] if p["month"] == "2026-05")
    assert may["income"] == pytest.approx(4500.00)
    assert may["total_spend"] == pytest.approx(995.50)


def test_yearly_report_sums(client, admin_user, month_data):
    login(client)
    data = client.get("/api/reports/yearly?year=2026").json()
    assert len(data["months"]) == 12
    assert data["total_income"] == pytest.approx(4500.00)
    assert data["total_spend"] == pytest.approx(995.50)


def test_report_values_are_numbers_not_strings(client, admin_user, month_data):
    """Decimal values must serialize as JSON numbers, not strings."""
    login(client)
    data = client.get("/api/reports/monthly?year=2026&month=5").json()
    assert isinstance(data["income"], float)
    assert isinstance(data["total_spend"], float)
    assert isinstance(data["by_category"][0]["total"], float)
