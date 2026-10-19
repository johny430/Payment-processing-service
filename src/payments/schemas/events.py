from uuid import UUID

from pydantic import BaseModel


class PaymentCreatedEventSchema(BaseModel):
    """Событие payments.new: платёж создан и ожидает обработки"""

    event_id: UUID  # совпадает с id записи outbox и message_id сообщения
    payment_id: UUID
