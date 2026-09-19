"""order reprocessing

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-19

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('orders', sa.Column('cycle', sa.Integer(), server_default='1', nullable=False))
    op.add_column('orders', sa.Column('cycle_attempts', sa.Integer(), server_default='0', nullable=False))
    # Pedidos que já existem estão na rodada 1: as tentativas da rodada são todas as feitas
    op.execute("UPDATE orders SET cycle_attempts = attempts")

    op.add_column('order_attempts', sa.Column('cycle', sa.Integer(), server_default='1', nullable=False))

    op.create_table('order_reprocesses',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('order_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.Column('requested_by_id', sa.Integer(), nullable=True),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('previous_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.ForeignKeyConstraint(['order_id'], ['orders.id'], name=op.f('fk_order_reprocesses_order_id_orders'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['requested_by_id'], ['users.id'], name=op.f('fk_order_reprocesses_requested_by_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_order_reprocesses'))
    )
    op.create_index(op.f('ix_order_reprocesses_order_id'), 'order_reprocesses', ['order_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_order_reprocesses_order_id'), table_name='order_reprocesses')
    op.drop_table('order_reprocesses')
    op.drop_column('order_attempts', 'cycle')
    op.drop_column('orders', 'cycle_attempts')
    op.drop_column('orders', 'cycle')
