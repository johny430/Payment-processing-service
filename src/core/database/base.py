import typing as t
from datetime import datetime

from sqlalchemy import DateTime, MetaData, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Единые имена ограничений и индексов, чтобы миграции Alembic были детерминированными
NAMING_CONVENTION = {
    'ix': 'ix_%(column_0_label)s',
    'uq': 'uq_%(table_name)s_%(column_0_name)s',
    'ck': 'ck_%(table_name)s_%(constraint_name)s',
    'fk': 'fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s',
    'pk': 'pk_%(table_name)s',
}


class Base(AsyncAttrs, DeclarativeBase):
    """Базовый класс моделей"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: t.ClassVar[dict[t.Any, t.Any]] = {
        datetime: DateTime(timezone=True),
        dict[str, t.Any]: JSONB,
    }


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), comment='Дата создания')
