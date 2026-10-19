import typing as t
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Path, status

from src.core.database.di import SessionDep
from src.payments.exceptions import IdempotencyKeyConflictError, PaymentNotFoundError
from src.payments.logic.use_cases import CreatePaymentUseCase, GetPaymentUseCase
from src.payments.schemas import PaymentAcceptedSchema, PaymentCreateSchema, PaymentSchema

router = APIRouter(prefix='/payments')

IdempotencyKey = t.Annotated[
    str,
    Header(
        alias='Idempotency-Key',
        min_length=1,
        max_length=255,
        description='Уникальный ключ запроса: повтор с тем же ключом не создаёт новый платёж',
    ),
]


@router.post(
    '',
    status_code=status.HTTP_202_ACCEPTED,
    response_model=PaymentAcceptedSchema,
    summary='Создание платежа',
    description='Платёж принимается в обработку асинхронно, результат придёт на webhook_url.',
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            'description': 'Невалидный запрос или Idempotency-Key использован с другими параметрами',
        },
    },
)
async def create_payment(
    data: PaymentCreateSchema,
    idempotency_key: IdempotencyKey,
    session: SessionDep,
) -> PaymentAcceptedSchema:
    try:
        payment = await CreatePaymentUseCase(session=session, data=data.to_dto(idempotency_key)).execute()
    except IdempotencyKeyConflictError as err:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail='Idempotency-Key уже использован для запроса с другими параметрами',
        ) from err
    return PaymentAcceptedSchema.from_dto(payment)


@router.get(
    '/{payment_id}',
    response_model=PaymentSchema,
    summary='Получение информации о платеже',
    responses={status.HTTP_404_NOT_FOUND: {'description': 'Платёж не найден'}},
)
async def get_payment(
    payment_id: t.Annotated[UUID, Path(description='ID платежа')],
    session: SessionDep,
) -> PaymentSchema:
    try:
        payment = await GetPaymentUseCase(session=session, payment_id=payment_id).execute()
    except PaymentNotFoundError as err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Платёж не найден') from err
    return PaymentSchema.from_dto(payment)
