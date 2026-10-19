class PaymentNotFoundError(Exception):
    """Платёж не найден"""


class IdempotencyKeyConflictError(Exception):
    """Idempotency-Key уже использован для запроса с другими параметрами"""


class WebhookDeliveryError(Exception):
    """Не удалось доставить webhook-уведомление"""
