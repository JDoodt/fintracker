from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from sqlalchemy import (
    Boolean, Date, DateTime, ForeignKey, Index, Integer,
    Numeric, String, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    pin_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="user")
    import_batches: Mapped[List["ImportBatch"]] = relationship("ImportBatch", back_populates="user")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent: Mapped[Optional["Category"]] = relationship("Category", remote_side="Category.id", back_populates="children")
    children: Mapped[List["Category"]] = relationship("Category", back_populates="parent")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="category")
    import_rules: Mapped[List["ImportRule"]] = relationship("ImportRule", back_populates="category")


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")
    import_batch_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("import_batches.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="expenses")
    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="expenses")
    import_batch: Mapped[Optional["ImportBatch"]] = relationship("ImportBatch", back_populates="expenses")

    __table_args__ = (
        Index("ix_expenses_date", "date"),
        Index("ix_expenses_category_id", "category_id"),
        Index("ix_expenses_user_id", "user_id"),
    )


class Income(Base):
    __tablename__ = "income"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    recurring: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("month", "label", name="uq_income_month_label"),
        Index("ix_income_month", "month"),
    )


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    profile_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("bank_profiles.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    user: Mapped["User"] = relationship("User", back_populates="import_batches")
    profile: Mapped[Optional["BankProfile"]] = relationship("BankProfile", back_populates="import_batches")
    expenses: Mapped[List["Expense"]] = relationship("Expense", back_populates="import_batch")


class BankProfile(Base):
    __tablename__ = "bank_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    date_col: Mapped[str] = mapped_column(String(100), nullable=False)
    amount_col: Mapped[str] = mapped_column(String(100), nullable=False)
    desc_col: Mapped[str] = mapped_column(String(100), nullable=False)
    date_format: Mapped[str] = mapped_column(String(50), nullable=False)
    encoding: Mapped[str] = mapped_column(String(50), nullable=False, default="utf-8")
    delimiter: Mapped[str] = mapped_column(String(5), nullable=False, default=",")
    skip_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    amount_sign_flip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    import_batches: Mapped[List["ImportBatch"]] = relationship("ImportBatch", back_populates="profile")


class ImportRule(Base):
    __tablename__ = "import_rules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pattern: Mapped[str] = mapped_column(String(255), nullable=False)
    is_regex: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    category_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    category: Mapped[Optional["Category"]] = relationship("Category", back_populates="import_rules")
