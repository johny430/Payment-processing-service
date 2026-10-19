import typing as t

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки сервиса, читаются из переменных окружения и файла .env"""

    APPLICATION_NAME: str = 'payment-processing-service'
    ENVIRONMENT: t.Literal['Prod', 'Local', 'Pytest'] = 'Local'
    LOG_LEVEL: t.Literal['DEBUG', 'INFO', 'WARNING', 'ERROR'] = 'INFO'

    # Статический ключ для доступа к API (заголовок X-API-Key)
    API_KEY: SecretStr

    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_USERNAME: str = 'postgres'
    DB_PASSWORD: SecretStr = SecretStr('postgres')
    DB_NAME: str = 'payments'
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 10

    RABBITMQ_HOST: str = 'localhost'
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = 'guest'
    RABBITMQ_PASSWORD: SecretStr = SecretStr('guest')
    RABBITMQ_VHOST: str = '/'
    RABBITMQ_PREFETCH_COUNT: int = 10  # сколько сообщений consumer обрабатывает одновременно
    RABBITMQ_PAYMENTS_EXCHANGE: str = 'payments'
    QUEUE_PAYMENTS_NEW: str = 'payments.new'  # очередь и routing key событий о новых платежах

    # Повторная обработка: всего попыток и базовая задержка (секунды), задержка растёт как base * 2^(n-1)
    PAYMENT_MAX_ATTEMPTS: int = Field(default=3, ge=1)
    PAYMENT_RETRY_BASE_DELAY: float = Field(default=1.0, gt=0)

    # Эмуляция платёжного шлюза
    GATEWAY_MIN_DELAY: float = Field(default=2.0, ge=0)
    GATEWAY_MAX_DELAY: float = Field(default=5.0, ge=0)
    GATEWAY_SUCCESS_RATE: float = Field(default=0.9, ge=0, le=1)

    WEBHOOK_TIMEOUT: float = Field(default=5.0, gt=0)

    OUTBOX_BATCH_SIZE: int = Field(default=100, ge=1)
    OUTBOX_POLL_INTERVAL: float = Field(default=1.0, gt=0)

    model_config: t.ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        extra='ignore',
        case_sensitive=True,
    )

    @property
    def postgres_connection_url(self) -> str:
        return (
            f'postgresql+asyncpg://{self.DB_USERNAME}:{self.DB_PASSWORD.get_secret_value()}'
            f'@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}'
        )

    @property
    def rabbitmq_connection_url(self) -> str:
        vhost = '' if self.RABBITMQ_VHOST == '/' else self.RABBITMQ_VHOST
        return (
            f'amqp://{self.RABBITMQ_USER}:{self.RABBITMQ_PASSWORD.get_secret_value()}'
            f'@{self.RABBITMQ_HOST}:{self.RABBITMQ_PORT}/{vhost}'
        )


settings = Settings()
