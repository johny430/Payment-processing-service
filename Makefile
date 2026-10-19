.PHONY: prepare
prepare:
	cp -n .env.example .env

.PHONY: sync
sync:
	uv sync

.PHONY: format
format:
	uv run ruff format .
	uv run ruff check --fix .

.PHONY: lint
lint:
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy .

.PHONY: test
test:
	uv run pytest -vv --cov --cov-report=term-missing

.PHONY: up
up:
	docker compose up -d postgres rabbitmq

.PHONY: down
down:
	docker compose down

.PHONY: compose-up
compose-up:
	docker compose up -d --build

.PHONY: compose-down
compose-down:
	docker compose down -v

.PHONY: migrate
migrate:
	uv run alembic upgrade head

.PHONY: revision
revision:
	uv run alembic revision --autogenerate -m "$(msg)"

.PHONY: runserver
runserver:
	uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: consumer
consumer:
	uv run faststream run src.consumer:app

.PHONY: relay
relay:
	uv run faststream run src.outbox_relay:app

.PHONY: pyclean
pyclean:
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
