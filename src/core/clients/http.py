import httpx


class HTTPXClientProvider:
    """
    Ленивый singleton httpx.AsyncClient.

    Клиент создаётся при первом обращении (внутри работающего event loop)
    и переиспользует пул соединений между запросами; закрывается явно при остановке приложения.
    """

    def __init__(self, timeout: float) -> None:
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def __call__(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
