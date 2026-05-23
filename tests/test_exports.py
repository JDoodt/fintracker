import csv
import io
import json
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import Category, Expense, Income
from tests.conftest import login


@pytest.fixture()
def export_data(db, admin_user, seeded_categories):
    food_id = seeded_categories["food"].id

    db.add(Income(month="2026-04", amount=Decimal("3000.00"), label="Salary", recurring=True))
    db.add(Income(month="2026-05", amount=Decimal("3500.00"), label="Salary", recurring=True))
    db.add(Income(month="2026-05", amount=Decimal("200.00"), label="Bonus", recurring=False))

    expenses = [
        Expense(user_id=admin_user.id, date=date(2026, 4, 10),
                amount=Decimal("50.00"), category_id=food_id,
                description="April groceries", source="manual",
                created_at=datetime.now(timezone.utc)),
        Expense(user_id=admin_user.id, date=date(2026, 5, 5),
                amount=Decimal("120.99"), category_id=food_id,
                description="May groceries", recurring=True, source="manual",
                created_at=datetime.now(timezone.utc)),
        Expense(user_id=admin_user.id, date=date(2026, 5, 20),
                amount=Decimal("9.99"), category_id=None,
                description="Mystery charge", source="import",
                created_at=datetime.now(timezone.utc)),
    ]
    for e in expenses:
        db.add(e)
    db.flush()


# ─── CSV tests ────────────────────────────────────────────────────────────────

def test_csv_export_status_and_content_type(client, admin_user, export_data):
    login(client)
    resp = client.get("/api/export/csv?from=2026-04-01&to=2026-05-31")
    assert resp.status_code == 200
    assert "text/csv" in resp.headers["content-type"]
    assert "attachment" in resp.headers["content-disposition"]


def test_csv_parses_cleanly(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-04-01&to=2026-05-31").content
    # Strip UTF-8 BOM if present
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    assert len(rows) > 0


def test_csv_has_required_columns(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-04-01&to=2026-05-31").content
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    expected = {"type", "date", "amount", "category", "description", "label", "user", "recurring", "source"}
    assert expected.issubset(set(reader.fieldnames))


def test_csv_expense_rows_correct(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-04-01&to=2026-05-31").content
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))

    expense_rows = [r for r in rows if r["type"] == "expense"]
    assert len(expense_rows) == 3

    # Sorted by date
    dates = [r["date"] for r in expense_rows]
    assert dates == sorted(dates)

    may_groceries = next(r for r in expense_rows if r["description"] == "May groceries")
    assert may_groceries["amount"] == "120.99"
    assert may_groceries["recurring"] == "yes"
    assert may_groceries["category"] == "Food"
    assert may_groceries["user"] == "admin"


def test_csv_income_rows_correct(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-04-01&to=2026-05-31").content
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))

    income_rows = [r for r in rows if r["type"] == "income"]
    assert len(income_rows) == 3  # April salary + May salary + May bonus

    salary_rows = [r for r in income_rows if r["label"] == "Salary"]
    assert len(salary_rows) == 2
    amounts = {r["date"]: r["amount"] for r in salary_rows}
    assert amounts["2026-04"] == "3000.00"
    assert amounts["2026-05"] == "3500.00"


def test_csv_date_range_filters_expenses(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-05-01&to=2026-05-31").content
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))

    expense_rows = [r for r in rows if r["type"] == "expense"]
    descriptions = [r["description"] for r in expense_rows]
    assert "April groceries" not in descriptions
    assert "May groceries" in descriptions


def test_csv_date_range_filters_income(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/csv?from=2026-05-01&to=2026-05-31").content
    text = raw.decode("utf-8-sig")
    rows = list(csv.DictReader(io.StringIO(text)))

    income_rows = [r for r in rows if r["type"] == "income"]
    months = [r["date"] for r in income_rows]
    assert "2026-04" not in months
    assert "2026-05" in months


# ─── JSON tests ───────────────────────────────────────────────────────────────

def test_json_export_roundtrips(client, admin_user, export_data):
    login(client)
    raw = client.get("/api/export/json?from=2026-04-01&to=2026-05-31").content
    data = json.loads(raw)  # must not raise
    assert "expenses" in data
    assert "income" in data
    assert "categories" in data


def test_json_amounts_are_numbers(client, admin_user, export_data):
    """Decimal values must be JSON numbers, not strings."""
    login(client)
    data = client.get("/api/export/json?from=2026-04-01&to=2026-05-31").json()
    for e in data["expenses"]:
        assert isinstance(e["amount"], float), f"amount is {type(e['amount'])}"
    for r in data["income"]:
        assert isinstance(r["amount"], float)


def test_json_expense_fields(client, admin_user, export_data, seeded_categories):
    login(client)
    data = client.get("/api/export/json?from=2026-05-01&to=2026-05-31").json()

    may_groceries = next(e for e in data["expenses"] if e["description"] == "May groceries")
    assert may_groceries["amount"] == pytest.approx(120.99)
    assert may_groceries["recurring"] is True
    assert may_groceries["category"] == "Food"
    assert may_groceries["category_id"] == seeded_categories["food"].id
    assert may_groceries["user"] == "admin"
    assert may_groceries["source"] == "manual"

    mystery = next(e for e in data["expenses"] if e["description"] == "Mystery charge")
    assert mystery["category"] is None
    assert mystery["source"] == "import"


def test_json_income_fields(client, admin_user, export_data):
    login(client)
    data = client.get("/api/export/json?from=2026-05-01&to=2026-05-31").json()

    salary = next(r for r in data["income"] if r["label"] == "Salary")
    assert salary["month"] == "2026-05"
    assert salary["amount"] == pytest.approx(3500.00)
    assert salary["recurring"] is True


def test_json_categories_included(client, admin_user, export_data, seeded_categories):
    login(client)
    data = client.get("/api/export/json?from=2026-05-01&to=2026-05-31").json()
    names = {c["name"] for c in data["categories"]}
    assert "Food" in names
    assert "Essentials" in names


def test_json_date_range_filters(client, admin_user, export_data):
    login(client)
    data = client.get("/api/export/json?from=2026-05-01&to=2026-05-31").json()
    descriptions = [e["description"] for e in data["expenses"]]
    assert "April groceries" not in descriptions
    assert "May groceries" in descriptions


def test_json_metadata_fields(client, admin_user, export_data):
    login(client)
    data = client.get("/api/export/json?from=2026-04-01&to=2026-05-31").json()
    assert data["from"] == "2026-04-01"
    assert data["to"] == "2026-05-31"
    assert "exported_at" in data


def test_export_requires_auth(client):
    resp = client.get("/api/export/csv", follow_redirects=False)
    assert resp.status_code in (302, 303)
    resp = client.get("/api/export/json", follow_redirects=False)
    assert resp.status_code in (302, 303)
