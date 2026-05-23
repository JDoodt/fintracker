import pytest
from datetime import datetime, timezone
from app.models import ImportRule, Category
from app.services.categorizer import categorize


@pytest.fixture()
def categories(db):
    food = Category(name="Food", color="#f59e0b")
    transport = Category(name="Transport", color="#10b981")
    db.add_all([food, transport])
    db.flush()
    return {"food": food, "transport": transport}


def test_substring_match(db, categories):
    db.add(ImportRule(
        pattern="rewe",
        is_regex=False,
        category_id=categories["food"].id,
        priority=0,
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    assert categorize("REWE Markt Berlin", db) == categories["food"].id


def test_case_insensitive_match(db, categories):
    db.add(ImportRule(
        pattern="UBER",
        is_regex=False,
        category_id=categories["transport"].id,
        priority=0,
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    assert categorize("Uber trip downtown", db) == categories["transport"].id


def test_regex_match(db, categories):
    db.add(ImportRule(
        pattern=r"^BVG\s+\d+",
        is_regex=True,
        category_id=categories["transport"].id,
        priority=5,
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    assert categorize("BVG 12345 Monatskarte", db) == categories["transport"].id


def test_unmatched_returns_none(db):
    result = categorize("Random unknown merchant XYZ", db)
    assert result is None


def test_priority_order(db, categories):
    """Higher priority rule wins when both patterns match."""
    db.add(ImportRule(
        pattern="lidl",
        is_regex=False,
        category_id=categories["transport"].id,  # wrong category, low prio
        priority=0,
        created_at=datetime.now(timezone.utc),
    ))
    db.add(ImportRule(
        pattern="lidl",
        is_regex=False,
        category_id=categories["food"].id,  # correct category, high prio
        priority=10,
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()
    assert categorize("Lidl Filiale 001", db) == categories["food"].id
