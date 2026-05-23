"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # users table
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('pin_hash', sa.String(length=256), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # categories table
    op.create_table('categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('archived', sa.Boolean(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['parent_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # bank_profiles table
    op.create_table('bank_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('date_col', sa.String(length=100), nullable=False),
        sa.Column('amount_col', sa.String(length=100), nullable=False),
        sa.Column('desc_col', sa.String(length=100), nullable=False),
        sa.Column('date_format', sa.String(length=50), nullable=False),
        sa.Column('encoding', sa.String(length=50), nullable=False, server_default='utf-8'),
        sa.Column('delimiter', sa.String(length=5), nullable=False, server_default=','),
        sa.Column('skip_rows', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('amount_sign_flip', sa.Boolean(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # import_batches table
    op.create_table('import_batches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('profile_id', sa.Integer(), nullable=True),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('row_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['profile_id'], ['bank_profiles.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # import_rules table
    op.create_table('import_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('pattern', sa.String(length=255), nullable=False),
        sa.Column('is_regex', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    # expenses table
    op.create_table('expenses',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('category_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.String(length=500), nullable=True),
        sa.Column('recurring', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('source', sa.String(length=20), nullable=False, server_default='manual'),
        sa.Column('import_batch_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['category_id'], ['categories.id'], ),
        sa.ForeignKeyConstraint(['import_batch_id'], ['import_batches.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_expenses_date', 'expenses', ['date'])
    op.create_index('ix_expenses_category_id', 'expenses', ['category_id'])
    op.create_index('ix_expenses_user_id', 'expenses', ['user_id'])

    # income table
    op.create_table('income',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('month', sa.String(length=7), nullable=False),
        sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=False),
        sa.Column('recurring', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('month', 'label', name='uq_income_month_label')
    )
    op.create_index('ix_income_month', 'income', ['month'])


def downgrade() -> None:
    op.drop_index('ix_income_month', table_name='income')
    op.drop_table('income')
    op.drop_index('ix_expenses_user_id', table_name='expenses')
    op.drop_index('ix_expenses_category_id', table_name='expenses')
    op.drop_index('ix_expenses_date', table_name='expenses')
    op.drop_table('expenses')
    op.drop_table('import_rules')
    op.drop_table('import_batches')
    op.drop_table('bank_profiles')
    op.drop_table('categories')
    op.drop_table('users')
