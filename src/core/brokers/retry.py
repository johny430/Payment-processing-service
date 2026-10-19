import typing as t

from src.core.settings.log import get_logger

if t.TYPE_CHECKING:
    from collections.abc import Sequence

    from faststream.rabbit.message import RabbitMessage
    from faststream.rabbit.publisher import RabbitPublisher

logger = get_logger(__name__)

ATTEMPT_HEADER = 'x-attempt'


class DelayedRetryPolicy:
    """
    Повторная обработка сообщений через retry-очереди с TTL.

    После неудачной попытки N (если N меньше максимума) сообщение публикуется в retry-очередь N,
    а исходное подтверждается. По истечении TTL RabbitMQ через dead-letter exchange возвращает
    его в рабочую очередь. Номер попытки передаётся в заголовке x-attempt.
    Ожидание происходит в брокере: consumer не простаивает, повторы переживают рестарт.
    """

    def __init__(self, retry_publishers: 'Sequence[RabbitPublisher]') -> None:
        # publisher с индексом i публикует в retry-очередь после неудачной попытки i + 1
        self._retry_publishers = tuple(retry_publishers)

    @property
    def max_attempts(self) -> int:
        return len(self._retry_publishers) + 1

    @staticmethod
    def get_attempt(message: 'RabbitMessage') -> int:
        """Номер текущей попытки обработки (начиная с 1)"""
        return int(message.headers.get(ATTEMPT_HEADER, 1))

    async def schedule_retry(self, message: 'RabbitMessage') -> bool:
        """Отправка сообщения на повторную обработку; False — попытки исчерпаны"""
        attempt = self.get_attempt(message)
        if attempt >= self.max_attempts:
            logger.error('Попытки обработки исчерпаны', message_id=message.message_id, attempt=attempt)
            return False

        await self._retry_publishers[attempt - 1].publish(
            message.body,
            headers={ATTEMPT_HEADER: attempt + 1},
            content_type=message.content_type,
            message_id=message.message_id,
            correlation_id=message.correlation_id,
            persist=True,
        )
        logger.warning('Сообщение отправлено на повторную обработку', message_id=message.message_id, attempt=attempt)
        return True
