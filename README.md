# Payment Processing Service

Микросервис асинхронного процессинга платежей. Принимает запрос на оплату, обрабатывает его через
эмуляцию внешнего платёжного шлюза и уведомляет клиента о результате через webhook.

**Стек:** FastAPI + Pydantic v2, SQLAlchemy 2.0 (async, asyncpg), PostgreSQL, RabbitMQ (FastStream),
Alembic, uv, pytest, Docker Compose, GitHub Actions.

## Архитектура

```
POST /api/v1/payments
        │
        ▼
       api ── одна транзакция ──► PostgreSQL: payments + outbox
        │                                   │
        └─► 202 Accepted                    │ SELECT … FOR UPDATE SKIP LOCKED
                                            ▼
                                       outbox-relay
                                            │ publish + publisher confirm
                                            ▼
                      exchange payments ── payments.new ──► queue payments.new
                                                                   │
                                                                   ▼
                                                               consumer
                                      шлюз (2–5 с, 90 % успех) ◄───┤
                                      UPDATE payments.status   ◄───┤
                                      POST webhook_url         ◄───┘
                                                                   │ ошибка
                              ┌────────────────────────────────────┴──────────────┐
                              ▼ попытка < 3                                        ▼ попытка = 3
      payments.retry ─► payments.new.retry.N (TTL 1 с, 2 с)       reject ─► payments.dlx ─► payments.new.dlq
                              │ по истечении TTL (DLX)
                              └─► payments ─► payments.new
```

| Сервис         | Точка входа                    | Назначение                                                        |
|----------------|--------------------------------|-------------------------------------------------------------------|
| `api`          | `src/main.py`                  | REST API: создание и получение платежей                           |
| `outbox-relay` | `src/outbox_relay.py`          | Перенос событий из таблицы `outbox` в RabbitMQ                    |
| `consumer`     | `src/consumer.py`              | Единственный обработчик `payments.new`: шлюз → статус → webhook   |
| `migrations`   | `alembic upgrade head`         | Одноразовый запуск миграций перед стартом приложений              |
| `postgres`, `rabbitmq` | —                      | Инфраструктура                                                    |
| `webhook-receiver` | `tools/webhook_receiver.py` | Демонстрационный приёмник webhook (не часть сервиса)             |

### Структура кода

Код разбит по доменам, внутри домена — по слоям (как в `aura_consumables`):

```
src/
  core/                 инфраструктура: settings, database, brokers (топология, retry), api (auth, роутеры)
  payments/
    api/                эндпоинты: доменные исключения → HTTP-ответы
    logic/use_cases/    сценарии: CreatePayment, GetPayment, ProcessPayment
    repositories/       доступ к БД, возвращают DTO
    models/ dtos/ schemas/
    clients/            платёжный шлюз (эмуляция) и отправка webhook
    brokers.py          подписчик RabbitMQ
    di.py               зависимости подписчика: шлюз, отправитель webhook, HTTP-клиент
  outbox/               transactional outbox: модель, репозиторий, публикация пачки, relay-цикл
  migrations/           Alembic
```

Сценарии управляют транзакцией сами, репозитории `commit` не делают — поэтому платёж и событие outbox
фиксируются атомарно. Зависимости сценариев (репозитории, шлюз, отправитель webhook) передаются
через конструктор и подменяются в тестах.

## Гарантии доставки

### Transactional outbox
`POST /payments` в одной транзакции создаёт платёж и запись в `outbox`. Если транзакция откатилась —
события нет; если брокер недоступен — платёж всё равно принят, событие ждёт в `outbox`.

`outbox-relay` в цикле выбирает неопубликованные события
`SELECT … WHERE published_at IS NULL ORDER BY created_at LIMIT N FOR UPDATE SKIP LOCKED`,
публикует их (persistent-сообщения, publisher confirms, `mandatory` + ошибка при немаршрутизируемом
сообщении) и только после подтверждения брокера ставит `published_at`. При ошибке публикации у события
растёт `attempts` и сохраняется `last_error`, пачка прерывается, relay повторяет попытку через
`OUTBOX_POLL_INTERVAL`. `SKIP LOCKED` позволяет запускать несколько реплик relay.

Гарантия — **at-least-once**: при падении между публикацией и commit событие уйдёт повторно.
Дубли безопасны, потому что обработка идемпотентна (см. ниже). `message_id` сообщения равен id события.

### Идемпотентность
* **API.** Заголовок `Idempotency-Key` обязателен, на колонке — уникальный индекс. Вставка идёт через
  `INSERT … ON CONFLICT (idempotency_key) DO NOTHING RETURNING`, поэтому гонку параллельных запросов
  разрешает БД (без ловли `IntegrityError`).
  * повтор с тем же ключом и теми же параметрами → `202` с тем же `payment_id`, новый платёж и событие не создаются;
  * тот же ключ с другими параметрами → `422` (как предлагает IETF draft *The Idempotency-Key HTTP Header Field*).
* **Consumer.** Шлюз вызывается только для платежа в статусе `pending`. Переход в итоговый статус — условный
  `UPDATE … WHERE status = 'pending'`: повторная доставка или параллельный consumer не перепишут результат.

### Retry и Dead Letter Queue
Повторы выполняются **через брокер**, а не `sleep` в обработчике: consumer не простаивает, отложенные
сообщения переживают рестарт.

| Объект                    | Тип                    | Назначение                                                                 |
|---------------------------|------------------------|----------------------------------------------------------------------------|
| `payments`                | exchange (direct)      | Основной exchange, routing key `payments.new`                              |
| `payments.new`            | queue                  | Рабочая очередь; `x-dead-letter-exchange = payments.dlx`                   |
| `payments.retry`          | exchange (direct)      | Отложенные повторы                                                         |
| `payments.new.retry.N`    | queue, `x-message-ttl` | Ожидание перед попыткой N+1: `base * 2^(N-1)` (1 с, 2 с); по TTL → `payments` |
| `payments.dlx`            | exchange (direct)      | Dead letter exchange                                                       |
| `payments.new.dlq`        | queue                  | Сообщения, не обработанные за все попытки                                  |

1. Ошибка обработки (недоступный webhook, сбой БД) — сообщение публикуется в `payments.new.retry.{N}`
   с заголовком `x-attempt = N+1`, исходное подтверждается.
2. По истечении TTL RabbitMQ возвращает его через DLX в `payments.new`.
3. После `PAYMENT_MAX_ATTEMPTS` (по умолчанию 3) неудачных попыток исключение пробрасывается, FastStream
   делает `reject(requeue=False)`, и RabbitMQ перекладывает сообщение в `payments.new.dlq`.
4. Платёж, которого нет в БД, повторять бессмысленно — такое сообщение сразу уходит в DLQ.

Для каждой ступени задержки — отдельная очередь с фиксированным TTL: при per-message TTL в одной очереди
сообщения истекают только из её головы, и короткая задержка ждала бы длинную.

Если упала только отправка webhook, повтор не проводит платёж заново: статус уже зафиксирован, повторяется
только уведомление. Доставка webhook — at-least-once, получателю стоит дедуплицировать по `payment_id`.

## Запуск

### Docker Compose
```bash
docker compose up -d --build
```
Поднимутся postgres, rabbitmq, migrations, api, outbox-relay, consumer и webhook-receiver.

* API и Swagger: http://localhost:8000/docs
* RabbitMQ Management: http://localhost:15672 (guest / guest)
* Полученные демо-приёмником webhook: http://localhost:8081/webhooks

API-ключ по умолчанию — `change-me`; переопределяется переменной `API_KEY`. Если стандартные порты заняты,
задайте `POSTGRES_HOST_PORT`, `RABBITMQ_HOST_PORT`, `RABBITMQ_MANAGEMENT_HOST_PORT`, `API_HOST_PORT`,
`WEBHOOK_RECEIVER_HOST_PORT` (в окружении или в `.env`, см. `.env.example`).

```bash
docker compose logs -f consumer outbox-relay   # логи обработки (JSON)
docker compose down -v                         # остановить и удалить данные
```

### Локально (uv)
```bash
make prepare     # .env из .env.example
make sync        # uv sync
make up          # postgres + rabbitmq в Docker
make migrate     # alembic upgrade head
make runserver   # API на :8000
make relay       # outbox relay
make consumer    # consumer
```

## Примеры запросов

Создание платежа:
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: change-me' \
  -H 'Idempotency-Key: order-42' \
  -H 'Content-Type: application/json' \
  -d '{
        "amount": "1500.00",
        "currency": "RUB",
        "description": "Оплата заказа №42",
        "metadata": {"order_id": 42},
        "webhook_url": "http://webhook-receiver:8080/webhook"
      }'
```
```json
HTTP/1.1 202 Accepted
{"payment_id": "7a2de23f-310e-4141-8397-2a3254014a34", "status": "pending", "created_at": "2026-10-19T12:23:46.722311Z"}
```

Повтор с тем же `Idempotency-Key` вернёт тот же ответ; с тем же ключом, но другим телом — `422`.

Получение платежа (через 2–5 секунд статус станет `succeeded` или `failed`):
```bash
curl http://localhost:8000/api/v1/payments/7a2de23f-310e-4141-8397-2a3254014a34 -H 'X-API-Key: change-me'
```
```json
{
  "payment_id": "7a2de23f-310e-4141-8397-2a3254014a34",
  "amount": "1500.00",
  "currency": "RUB",
  "description": "Оплата заказа №42",
  "metadata": {"order_id": 42},
  "status": "succeeded",
  "idempotency_key": "order-42",
  "webhook_url": "http://webhook-receiver:8080/webhook",
  "created_at": "2026-10-19T12:23:46.722311Z",
  "processed_at": "2026-10-19T12:23:52.024793Z"
}
```

Webhook, который получит клиент:
```json
{
  "payment_id": "7a2de23f-310e-4141-8397-2a3254014a34",
  "status": "succeeded",
  "amount": "1500.00",
  "currency": "RUB",
  "metadata": {"order_id": 42},
  "processed_at": "2026-10-19T12:23:52.024793Z"
}
```

Демонстрация retry и DLQ — webhook, который всегда отвечает 500:
```bash
curl -X POST http://localhost:8000/api/v1/payments \
  -H 'X-API-Key: change-me' -H 'Idempotency-Key: order-fail-1' -H 'Content-Type: application/json' \
  -d '{"amount": "99.90", "currency": "USD", "description": "Webhook всегда падает",
       "webhook_url": "http://webhook-receiver:8080/webhook/fail"}'

docker compose logs consumer | grep attempt                                   # попытки 1, 2, 3 с задержками 1 с и 2 с
curl -s -u guest:guest http://localhost:15672/api/queues/%2F/payments.new.dlq  # messages: 1
```

| Код | Когда                                                                    |
|-----|--------------------------------------------------------------------------|
| 202 | Платёж принят (или повтор с тем же `Idempotency-Key`)                    |
| 401 | Нет заголовка `X-API-Key` или ключ неверный                              |
| 404 | Платёж не найден                                                         |
| 422 | Невалидное тело или заголовок; `Idempotency-Key` с другими параметрами  |

## Тесты

Тесты работают с настоящими PostgreSQL и RabbitMQ:
```bash
make up      # postgres + rabbitmq
make test    # uv run pytest -vv --cov
make lint    # ruff format --check, ruff check, mypy
```

* Схема тестовой БД `payments_test` создаётся настоящими миграциями Alembic; отдельный тест проверяет,
  что модели и миграции не расходятся.
* Брокер в тестах использует отдельные имена (`test.payments*`), поэтому не конфликтует с запущенным compose.
* `tests/test_payments`: API (идемпотентность, валидация, авторизация), сценарии (в том числе гонка
  10 параллельных запросов с одним ключом и конкурентная обработка), репозиторий, клиенты, consumer на `TestRabbitBroker`.
* `tests/test_outbox`: публикация пачки, ошибки брокера, `SKIP LOCKED` при параллельных relay, relay-цикл.
* `tests/test_integration`: сквозные сценарии на настоящем RabbitMQ (API → outbox → relay → consumer → webhook,
  временный сбой webhook, попадание в DLQ после всех попыток).

CI (`.github/workflows/ci.yml`): линтеры и mypy, тесты с сервисами postgres и rabbitmq, сборка Docker-образа.

## Переменные окружения

| Переменная                  | По умолчанию                 | Описание                                         |
|-----------------------------|------------------------------|--------------------------------------------------|
| `API_KEY`                   | — (обязательна)              | Статический ключ для заголовка `X-API-Key`       |
| `ENVIRONMENT`               | `Local`                      | `Prod` включает JSON-логи                        |
| `DB_HOST` / `DB_PORT` / `DB_NAME` | `localhost` / `5432` / `payments` | PostgreSQL                          |
| `DB_USERNAME` / `DB_PASSWORD` | `postgres` / `postgres`    |                                                  |
| `RABBITMQ_HOST` / `RABBITMQ_PORT` / `RABBITMQ_VHOST` | `localhost` / `5672` / `/` | RabbitMQ                   |
| `RABBITMQ_USER` / `RABBITMQ_PASSWORD` | `guest` / `guest`  |                                                  |
| `RABBITMQ_PREFETCH_COUNT`   | `10`                         | Сколько сообщений consumer обрабатывает одновременно |
| `PAYMENT_MAX_ATTEMPTS`      | `3`                          | Попыток обработки до отправки в DLQ              |
| `PAYMENT_RETRY_BASE_DELAY`  | `1.0`                        | Базовая задержка повтора, с (растёт как `base * 2^(n-1)`) |
| `GATEWAY_MIN_DELAY` / `GATEWAY_MAX_DELAY` | `2` / `5`      | Время обработки в эмуляции шлюза, с              |
| `GATEWAY_SUCCESS_RATE`      | `0.9`                        | Доля успешных платежей в эмуляции                |
| `WEBHOOK_TIMEOUT`           | `5`                          | Таймаут запроса webhook, с                       |
| `OUTBOX_BATCH_SIZE`         | `100`                        | Размер пачки relay                               |
| `OUTBOX_POLL_INTERVAL`      | `1.0`                        | Пауза relay при пустом outbox, с                 |

Изменение `PAYMENT_MAX_ATTEMPTS` или `PAYMENT_RETRY_BASE_DELAY` меняет аргументы retry-очередей: RabbitMQ
не позволяет переобъявить очередь с другими аргументами, поэтому старые retry-очереди нужно удалить.
