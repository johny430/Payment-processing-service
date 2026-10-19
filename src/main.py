import typing as t
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.api.routers import api_v1_router
from src.core.database.di import engine
from src.core.settings.log import setup_logging
from src.healthcheck import api as healthcheck_api

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI) -> t.AsyncIterator[None]:
    yield
    await engine.dispose()


app = FastAPI(
    title='Payment Processing Service',
    description='Асинхронный процессинг платежей: приём, обработка через платёжный шлюз и webhook-уведомления',
    version='0.1.0',
    lifespan=lifespan,
)
app.include_router(healthcheck_api.router)
app.include_router(api_v1_router)
