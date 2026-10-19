from enum import StrEnum


class PaymentStatusEnum(StrEnum):
    """Статус платежа"""

    PENDING = 'pending'  # принят, ожидает обработки
    SUCCEEDED = 'succeeded'
    FAILED = 'failed'


class CurrencyEnum(StrEnum):
    """Поддерживаемые валюты (ISO 4217)"""

    RUB = 'RUB'
    USD = 'USD'
    EUR = 'EUR'
