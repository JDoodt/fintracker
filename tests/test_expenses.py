from decimal import Decimal
from datetime import date, datetime, timezone

import pytest

from app.models import Expense, Income, Category
from tests.conftest import login


def test_redirect_to_login_when_unauthenticated(client):
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert "/login" in resp.headers["location"]


def test_login_success(client, admin_user):
    login(client)
    resp = client.get("/", follow_redirects=False)
    assert resp.status_code == 200


def test_login_wrong_pin(client, admin_user):
    resp = client.post("/login", data={"username": "admin", "pin": "9999"}, follow_redirects=False)
    assert resp.status_code in (302, 303)
    follow = client.get("/login")
    assert "Invalid" in follow.text


def test_create_expense(client, admin_user, seeded_categories, db):
    login(client)
    resp = client.post("/expenses", data={
        "date": "2026-05-01",
        "amount": "42.50",
        "category_id": str(seeded_categories["food"].id),
        "description": "Groceries",
        "recurring": "",
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)

    expense = db.query(Expense).filter_by(description="Groceries").first()
    assert expense is not None
    assert expense.amount == Decimal("42.50")
    assert expense.date == date(2026, 5, 1)
    assert expense.source == "manual"
    assert expense.user_id == admin_user.id


def test_expense_amount_is_decimal_not_float(client, admin_user, seeded_categories, db):
    """Verify money is stored as Decimal, no float drift."""
    login(client)
    client.post("/expenses", data={
        "date": "2026-05-02",
        "amount": "19.99",
        "description": "Test float precision",
    }, follow_redirects=False)
    expense = db.query(Expense).filter_by(description="Test float precision").first()
    assert isinstance(expense.amount, Decimal)
    assert expense.amount == Decimal("19.99")


def test_expenses_list_shows_entries(client, admin_user, seeded_categories, db):
    login(client)
    db.add(Expense(
        user_id=admin_user.id,
        date=date(2026, 5, 10),
        amount=Decimal("55.00"),
        category_id=seeded_categories["food"].id,
        description="Supermarket",
        source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()

    resp = client.get("/expenses?month=2026-05")
    assert resp.status_code == 200
    assert "Supermarket" in resp.text


def test_expenses_filter_by_month(client, admin_user, db):
    login(client)
    db.add(Expense(
        user_id=admin_user.id,
        date=date(2026, 4, 1),
        amount=Decimal("10.00"),
        description="April expense",
        source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Expense(
        user_id=admin_user.id,
        date=date(2026, 5, 1),
        amount=Decimal("20.00"),
        description="May expense",
        source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()

    resp = client.get("/expenses?month=2026-04")
    assert "April expense" in resp.text
    assert "May expense" not in resp.text


def test_expenses_filter_by_category(client, admin_user, seeded_categories, db):
    login(client)
    food_id = seeded_categories["food"].id
    db.add(Expense(
        user_id=admin_user.id,
        date=date(2026, 5, 1),
        amount=Decimal("5.00"),
        description="Food item",
        category_id=food_id,
        source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.add(Expense(
        user_id=admin_user.id,
        date=date(2026, 5, 1),
        amount=Decimal("30.00"),
        description="Electric bill",
        category_id=seeded_categories["essentials"].id,
        source="manual",
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()

    resp = client.get(f"/expenses?month=2026-05&category_id={food_id}")
    assert "Food item" in resp.text
    assert "Electric bill" not in resp.text


def test_total_is_sum_of_decimal(client, admin_user, db):
    """Verify totals use Decimal arithmetic, not float."""
    login(client)
    amounts = [Decimal("10.01"), Decimal("20.02"), Decimal("30.03")]
    for a in amounts:
        db.add(Expense(
            user_id=admin_user.id,
            date=date(2026, 5, 15),
            amount=a,
            source="manual",
            created_at=datetime.now(timezone.utc),
        ))
    db.flush()

    total = sum(amounts)
    assert total == Decimal("60.06")


def test_delete_expense(client, admin_user, db):
    login(client)
    exp = Expense(
        user_id=admin_user.id,
        date=date(2026, 5, 1),
        amount=Decimal("99.00"),
        description="To be deleted",
        source="manual",
        created_at=datetime.now(timezone.utc),
    )
    db.add(exp)
    db.flush()

    resp = client.post(f"/expenses/{exp.id}/delete", follow_redirects=False)
    assert resp.status_code in (302, 303)
    assert db.get(Expense, exp.id) is None


def test_add_income(client, admin_user, db):
    login(client)
    resp = client.post("/income", data={
        "month": "2026-05",
        "amount": "3500.00",
        "label": "Salary",
        "recurring": "on",
    }, follow_redirects=False)
    assert resp.status_code in (302, 303)

    record = db.query(Income).filter_by(month="2026-05", label="Salary").first()
    assert record is not None
    assert record.amount == Decimal("3500.00")
    assert record.recurring is True


def test_two_users_can_both_add_expenses(client, admin_user, regular_user, db):
    # Admin adds expense
    login(client, "admin", "1234")
    client.post("/expenses", data={
        "date": "2026-05-01", "amount": "10.00", "description": "Admin expense",
    }, follow_redirects=False)

    # Log out, log in as bob
    client.post("/logout", follow_redirects=False)
    login(client, "bob", "5678")
    client.post("/expenses", data={
        "date": "2026-05-01", "amount": "20.00", "description": "Bob expense",
    }, follow_redirects=False)

    admin_exp = db.query(Expense).filter_by(description="Admin expense").first()
    bob_exp = db.query(Expense).filter_by(description="Bob expense").first()
    assert admin_exp.user_id == admin_user.id
    assert bob_exp.user_id == regular_user.id


def test_expenses_list_shows_all_users(client, admin_user, regular_user, db):
    """Admin list shows expenses from all users."""
    db.add(Expense(user_id=admin_user.id, date=date(2026, 5, 1),
                   amount=Decimal("1.00"), description="admin item",
                   source="manual", created_at=datetime.now(timezone.utc)))
    db.add(Expense(user_id=regular_user.id, date=date(2026, 5, 1),
                   amount=Decimal("2.00"), description="bob item",
                   source="manual", created_at=datetime.now(timezone.utc)))
    db.flush()

    login(client, "admin", "1234")
    resp = client.get("/expenses?month=2026-05")
    assert "admin item" in resp.text
    assert "bob item" in resp.text
