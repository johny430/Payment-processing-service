from fastapi import APIRouter, Depends

from src.core.api.auth import verify_api_key
from src.payments.api.routers import payments_router

api_v1_router = APIRouter(prefix='/api/v1', dependencies=[Depends(verify_api_key)])
api_v1_router.include_router(payments_router)
