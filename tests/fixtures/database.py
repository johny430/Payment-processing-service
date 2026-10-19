import asyncio
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import make_url, text
from sqlalchemy.ext.asyncio import create_async_engine

from src.core.database.di import AsyncSessionLocal, engine
from src.core.settings import settings

ROOT_DIR = Path(__file__).resolve().parents[2]


async def execute_on_server(*statements: str) -> None:
    """Выполнение служебных команд в БД postgres (создание и удаление тестовой БД)"""
    server_url = make_url(settings.postgres_connection_url).set(database='postgres')
    admin_engine = create_async_engine(server_url, isolation_level='AUTOCOMMIT')
    async with admin_engine.connect() as conn:
        for statement in statements:
            await conn.execute(text(statement))
    await admin_engine.dispose()


@pytest.fixture(scope='session', autouse=True)
async def database():
    """Тестовая БД, схема которой создаётся настоящими миграциями Alembic"""
    assert settings.ENVIRONMENT == 'Pytest', 'Тесты пересоздают БД и запускаются только с ENVIRONMENT=Pytest'
    drop_statement = f'DROP DATABASE IF EXISTS "{settings.DB_NAME}" WITH (FORCE)'
    await execute_on_server(drop_statement, f'CREATE DATABASE "{settings.DB_NAME}"')
    # env.py Alembic сам запускает event loop, поэтому миграции выполняются в отдельном потоке
    await asyncio.to_thread(command.upgrade, Config(str(ROOT_DIR / 'alembic.ini')), 'head')

    yield

    await engine.dispose()
    await execute_on_server(drop_statement)


@pytest.fixture(autouse=True)
async def clean_tables(database):
    """
    Очистка таблиц после каждого теста.

    API, consumer и relay коммитят изменения в собственных сессиях,
    поэтому откат внешней транзакции здесь не подходит.
    """
    yield
    async with engine.begin() as conn:
        await conn.execute(text('TRUNCATE payments, outbox'))


@pytest.fixture
async def session():
    async with AsyncSessionLocal() as session:
        yield session
