from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.ext.asyncio import AsyncSession


class BaseFactory(SQLAlchemyModelFactory):
    """Асинхронная фабрика: объект коммитится, чтобы его видели сессии API, consumer и relay"""

    class Meta:
        abstract = True

    @classmethod
    async def create(cls, session: AsyncSession, **overrides):
        obj = cls.build(**overrides)
        session.add(obj)
        await session.commit()
        return obj

    @classmethod
    async def create_batch(cls, session: AsyncSession, size: int, **overrides) -> list:
        return [await cls.create(session, **overrides) for _ in range(size)]
