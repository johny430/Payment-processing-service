import typing as t

if t.TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class BaseSessionAsyncUseCase:
    """
    Базовый сценарий, работающий с сессией БД.

    Границы транзакции определяет сценарий: репозитории не делают commit сами,
    поэтому несколько изменений внутри одного сценария фиксируются атомарно.
    """

    def __init__(self, session: 'AsyncSession') -> None:
        self.session = session

    async def execute(self, *args: t.Any, **kwargs: t.Any) -> t.Any:
        raise NotImplementedError
