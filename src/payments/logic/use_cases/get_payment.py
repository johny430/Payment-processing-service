import typing as t

from src.core.use_cases.base import BaseSessionAsyncUseCase
from src.payments.exceptions import PaymentNotFoundError
from src.payments.repositories import PaymentRepository

if t.TYPE_CHECKING:
    from uuid import UUID

    from src.payments.dtos import PaymentDTO


class GetPaymentUseCase(BaseSessionAsyncUseCase):
    """Получение платежа по ID"""

    def __init__(
        self,
        payment_id: 'UUID',
        payment_repo: type[PaymentRepository] = PaymentRepository,
        *args: t.Any,
        **kwargs: t.Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.payment_id = payment_id
        self.payment_repo = payment_repo(self.session)

    async def execute(self) -> 'PaymentDTO':
        payment = await self.payment_repo.get_by_id(self.payment_id)
        if payment is None:
            raise PaymentNotFoundError
        return payment
