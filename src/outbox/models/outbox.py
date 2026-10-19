import typing as t
import uuid
from datetime import datetime

from sqlalchemy import Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.core.database.base import Base, CreatedAtMixin


class OutboxEvent(CreatedAtMixin, Base):
    """
    Событие transactional outbox.

    Записывается в той же транзакции, что и бизнес-изменение, а в брокер
    публикуется отдельным процессом (outbox relay). Так событие не теряется, если брокер
    недоступен, и не публикуется, если бизнес-транзакция откатилась.
    """

    __tablename__ = 'outbox'
    __table_args__ = (
        # Relay выбирает только неопубликованные события в порядке создания
        Index('ix_outbox_unpublished', 'created_at', postgresql_where=text('published_at IS NULL')),
    )
    __mapper_args__ = {'eager_defaults': True}  # server_default (created_at) читается сразу через RETURNING

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4, comment='Идентификатор события')
    event_type: Mapped[str] = mapped_column(String(255), comment='Тип события, он же routing key')
    payload: Mapped[dict[str, t.Any]] = mapped_column(comment='Тело события')
    published_at: Mapped[datetime | None] = mapped_column(comment='Дата публикации в брокер')
    attempts: Mapped[int] = mapped_column(
        default=0, server_default=text('0'), comment='Количество неудачных попыток публикации'
    )
    last_error: Mapped[str | None] = mapped_column(Text, comment='Последняя ошибка публикации')
