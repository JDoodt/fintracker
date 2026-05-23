import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base, User, Category
from app.auth import hash_pin
from app.db import get_db
from app.main import app

TEST_DB_URL = "sqlite:///:memory:"

_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
_SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)


@pytest.fixture(scope="session", autouse=True)
def create_tables():
    Base.metadata.create_all(_engine)
    yield
    Base.metadata.drop_all(_engine)


@pytest.fixture()
def db():
    connection = _engine.connect()
    transaction = connection.begin()
    session = _SessionLocal(bind=connection)
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture()
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def admin_user(db):
    user = User(
        name="admin",
        pin_hash=hash_pin("1234"),
        created_at=datetime.now(timezone.utc),
        is_admin=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def regular_user(db):
    user = User(
        name="bob",
        pin_hash=hash_pin("5678"),
        created_at=datetime.now(timezone.utc),
        is_admin=False,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def seeded_categories(db):
    food = Category(name="Food", color="#f59e0b")
    essentials = Category(name="Essentials", color="#3b82f6")
    db.add_all([food, essentials])
    db.flush()
    electricity = Category(name="Electricity", parent_id=essentials.id, color="#fbbf24")
    db.add(electricity)
    db.flush()
    return {"food": food, "essentials": essentials, "electricity": electricity}


def login(client, username="admin", pin="1234"):
    resp = client.post("/login", data={"username": username, "pin": pin}, follow_redirects=False)
    assert resp.status_code in (302, 303), f"Login failed: {resp.status_code}"
