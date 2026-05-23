from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator


# ---- User schemas ----

class UserCreate(BaseModel):
    name: str
    pin: str

    @field_validator("pin")
    @classmethod
    def pin_must_be_digits(cls, v: str) -> str:
        if not v.isdigit():
            raise ValueError("PIN must contain only digits")
        if not (4 <= len(v) <= 8):
            raise ValueError("PIN must be 4-8 digits")
        return v


class UserOut(BaseModel):
    id: int
    name: str
    created_at: datetime
    is_admin: bool

    model_config = {"from_attributes": True}


# ---- Category schemas ----

class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None
    color: Optional[str] = None


class CategoryOut(BaseModel):
    id: int
    name: str
    parent_id: Optional[int] = None
    color: Optional[str] = None
    archived: bool

    model_config = {"from_attributes": True}


class CategoryTree(CategoryOut):
    children: List["CategoryTree"] = []

    model_config = {"from_attributes": True}


CategoryTree.model_rebuild()


# ---- Expense schemas ----

class ExpenseCreate(BaseModel):
    date: date
    amount: Decimal
    category_id: Optional[int] = None
    description: Optional[str] = None
    recurring: bool = False

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class ExpenseOut(BaseModel):
    id: int
    user_id: int
    date: date
    amount: Decimal
    category_id: Optional[int] = None
    description: Optional[str] = None
    recurring: bool
    source: str
    import_batch_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExpenseFilter(BaseModel):
    year: Optional[int] = None
    month: Optional[int] = None
    category_id: Optional[int] = None
    from_date: Optional[date] = None
    to_date: Optional[date] = None


# ---- Income schemas ----

class IncomeCreate(BaseModel):
    month: str
    amount: Decimal
    label: str
    recurring: bool = True

    @field_validator("month")
    @classmethod
    def month_format(cls, v: str) -> str:
        import re
        if not re.match(r"^\d{4}-\d{2}$", v):
            raise ValueError("Month must be in YYYY-MM format")
        return v

    @field_validator("amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v


class IncomeOut(BaseModel):
    id: int
    month: str
    amount: Decimal
    label: str
    recurring: bool

    model_config = {"from_attributes": True}


# ---- Import schemas ----

class BankProfileCreate(BaseModel):
    name: str
    date_col: str
    amount_col: str
    desc_col: str
    date_format: str
    encoding: str = "utf-8"
    delimiter: str = ","
    skip_rows: int = 0
    amount_sign_flip: bool = False


class BankProfileOut(BaseModel):
    id: int
    name: str
    date_col: str
    amount_col: str
    desc_col: str
    date_format: str
    encoding: str
    delimiter: str
    skip_rows: int
    amount_sign_flip: bool

    model_config = {"from_attributes": True}


class ImportRowPreview(BaseModel):
    row_index: int
    date: Optional[date] = None
    amount: Optional[Decimal] = None
    description: Optional[str] = None
    category_id: Optional[int] = None
    raw: dict


class ImportPreview(BaseModel):
    rows: List[ImportRowPreview]
    filename: str
    profile_id: Optional[int] = None
    errors: List[str] = []


# ---- Report schemas ----

class CategorySpend(BaseModel):
    category_id: Optional[int]
    category_name: str
    total: Decimal


class MonthlyReport(BaseModel):
    year: int
    month: int
    income: Decimal
    total_spend: Decimal
    net: Decimal
    pct_spent: Optional[Decimal]
    by_category: List[CategorySpend]


class YearlyReport(BaseModel):
    year: int
    months: List[MonthlyReport]
    total_income: Decimal
    total_spend: Decimal


class TrendPoint(BaseModel):
    month: str  # YYYY-MM
    total_spend: Decimal
    income: Decimal


class TrendReport(BaseModel):
    points: List[TrendPoint]
