import asyncio
import random
import typing as t

from src.core.settings import settings
from src.payments.enums import PaymentStatusEnum

if t.TYPE_CHECKING:
    from src.payments.dtos import PaymentDTO


@t.runtime_checkable  # FastStream валидирует аргументы обработчика через isinstance
class PaymentGateway(t.Protocol):
    """Внешний платёжный шлюз"""

    async def charge(self, payment: 'PaymentDTO') -> PaymentStatusEnum:
        """Проведение платежа; возвращает итоговый статус"""
        ...


class EmulatedPaymentGateway:
    """Эмуляция платёжного шлюза: обработка занимает min_delay..max_delay секунд, success_rate операций успешны"""

    def __init__(
        self,
        min_delay: float = settings.GATEWAY_MIN_DELAY,
        max_delay: float = settings.GATEWAY_MAX_DELAY,
        success_rate: float = settings.GATEWAY_SUCCESS_RATE,
        rng: random.Random | None = None,
    ) -> None:
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.success_rate = success_rate
        self._rng = rng or random.Random()

    async def charge(self, payment: 'PaymentDTO') -> PaymentStatusEnum:
        await asyncio.sleep(self._rng.uniform(self.min_delay, self.max_delay))
        if self._rng.random() < self.success_rate:
            return PaymentStatusEnum.SUCCEEDED
        return PaymentStatusEnum.FAILED
