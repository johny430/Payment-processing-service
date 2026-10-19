from fastapi import APIRouter

from src.payments.api import payments

payments_router = APIRouter(tags=['Платежи'])
payments_router.include_router(payments.router)
