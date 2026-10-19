"""
001_create_payments_and_outbox

Revision ID: 70cc73ec6631
Revises:
Create Date: 2026-10-19 15:14:03.891556

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '70cc73ec6631'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'payments',
        sa.Column('id', sa.Uuid(), nullable=False, comment='Идентификатор платежа'),
        sa.Column('amount', sa.Numeric(precision=18, scale=2), nullable=False, comment='Сумма'),
        sa.Column('currency', sa.String(length=3), nullable=False, comment='Валюта'),
        sa.Column('description', sa.String(length=500), nullable=False, comment='Описание'),
        sa.Column(
            'metadata',
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
            comment='Дополнительные данные клиента',
        ),
        sa.Column('status', sa.String(length=16), nullable=False, comment='Статус'),
        sa.Column('idempotency_key', sa.String(length=255), nullable=False, comment='Ключ идемпотентности'),
        sa.Column('webhook_url', sa.String(length=2048), nullable=False, comment='URL для уведомления о результате'),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True, comment='Дата обработки'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Дата создания',
        ),
        sa.CheckConstraint('amount > 0', name=op.f('ck_payments_amount_positive')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_payments')),
        sa.UniqueConstraint('idempotency_key', name=op.f('uq_payments_idempotency_key')),
    )
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)

    op.create_table(
        'outbox',
        sa.Column('id', sa.Uuid(), nullable=False, comment='Идентификатор события'),
        sa.Column('event_type', sa.String(length=255), nullable=False, comment='Тип события, он же routing key'),
        sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False, comment='Тело события'),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True, comment='Дата публикации в брокер'),
        sa.Column(
            'attempts',
            sa.Integer(),
            server_default=sa.text('0'),
            nullable=False,
            comment='Количество неудачных попыток публикации',
        ),
        sa.Column('last_error', sa.Text(), nullable=True, comment='Последняя ошибка публикации'),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
            comment='Дата создания',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox')),
    )
    op.create_index(
        'ix_outbox_unpublished',
        'outbox',
        ['created_at'],
        unique=False,
        postgresql_where=sa.text('published_at IS NULL'),
    )


def downgrade() -> None:
    op.drop_index('ix_outbox_unpublished', table_name='outbox', postgresql_where=sa.text('published_at IS NULL'))
    op.drop_table('outbox')
    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_table('payments')
