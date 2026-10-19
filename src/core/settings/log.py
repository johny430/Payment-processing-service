import logging
import typing as t

import structlog

from src.core.settings import settings

if t.TYPE_CHECKING:
    from structlog.typing import EventDict, Processor


def _drop_color_message(_: t.Any, __: str, event_dict: 'EventDict') -> 'EventDict':
    """uvicorn дублирует сообщение с ANSI-цветами в extra — в логах оно не нужно"""
    event_dict.pop('color_message', None)
    return event_dict


def setup_logging() -> None:
    """
    Настройка structlog и стандартного logging.

    Логи библиотек (uvicorn, faststream, sqlalchemy) проходят через тот же форматтер,
    поэтому в проде весь вывод — JSON, а локально — читаемая консоль.
    FastStream получает обычный logging-логгер: со structlog-логгером он дублирует форматирование.
    """
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso', utc=True),
    ]
    # Для записей стандартного logging: контекст из extra (FastStream кладёт туда очередь и message_id)
    foreign_pre_chain: list[Processor] = [*shared_processors, structlog.stdlib.ExtraAdder(), _drop_color_message]
    renderer: Processor = (
        structlog.processors.JSONRenderer(ensure_ascii=False)
        if settings.ENVIRONMENT == 'Prod'
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=foreign_pre_chain,
            processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
        )
    )
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(settings.LOG_LEVEL)

    # uvicorn настраивает свои логгеры до импорта приложения — переключаем их на общий handler
    for name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        library_logger = logging.getLogger(name)
        library_logger.handlers.clear()
        library_logger.propagate = True


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.stdlib.get_logger(name)
