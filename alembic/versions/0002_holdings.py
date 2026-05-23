"""Add holdings and price_snapshots tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-23

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'holdings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column('added_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['added_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('ticker'),
    )

    op.create_table(
        'price_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('holding_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('price', sa.Numeric(precision=16, scale=6), nullable=False),
        sa.Column('currency', sa.String(length=10), nullable=False, server_default='EUR'),
        sa.Column('fetched_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['holding_id'], ['holdings.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('holding_id', 'date', name='uq_price_snapshot_holding_date'),
    )
    op.create_index('ix_price_snapshots_holding_date', 'price_snapshots', ['holding_id', 'date'])


def downgrade() -> None:
    op.drop_index('ix_price_snapshots_holding_date', table_name='price_snapshots')
    op.drop_table('price_snapshots')
    op.drop_table('holdings')
