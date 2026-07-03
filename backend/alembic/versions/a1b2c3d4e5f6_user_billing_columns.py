"""user billing columns

Revision ID: a1b2c3d4e5f6
Revises: 5f0f4f7b0528
Create Date: 2026-07-02
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '5f0f4f7b0528'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('users', sa.Column('plan', sa.String(length=16), nullable=False, server_default='free'))
    op.add_column('users', sa.Column('stripe_customer_id', sa.String(length=64), nullable=True))
    op.add_column('users', sa.Column('stripe_subscription_id', sa.String(length=64), nullable=True))
    op.create_index(op.f('ix_users_stripe_customer_id'), 'users', ['stripe_customer_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_stripe_customer_id'), table_name='users')
    op.drop_column('users', 'stripe_subscription_id')
    op.drop_column('users', 'stripe_customer_id')
    op.drop_column('users', 'plan')
