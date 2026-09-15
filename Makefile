# Convenience wrappers. Everything here is also documented in README.md.
.DEFAULT_GOAL := help
BACKEND := backend
FRONTEND := frontend
BOT := tgbot
PY := $(BACKEND)/.venv/bin/python
PIP := $(BACKEND)/.venv/bin/pip

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

## --- setup ---------------------------------------------------------------
.PHONY: install
install: install-backend install-frontend install-bot ## Install every dependency

.PHONY: install-backend
install-backend: ## Create the backend venv and install requirements
	python3 -m venv $(BACKEND)/.venv
	$(PIP) install -U pip
	$(PIP) install -r $(BACKEND)/requirements-dev.txt

.PHONY: install-frontend
install-frontend: ## npm install
	cd $(FRONTEND) && npm install

.PHONY: install-bot
install-bot: ## Create the bot venv and install requirements
	python3 -m venv $(BOT)/.venv
	$(BOT)/.venv/bin/pip install -U pip
	$(BOT)/.venv/bin/pip install -r $(BOT)/requirements.txt

## --- database ------------------------------------------------------------
.PHONY: migrate
migrate: ## Apply migrations
	cd $(BACKEND) && .venv/bin/python manage.py migrate

.PHONY: migrations
migrations: ## Create migrations
	cd $(BACKEND) && .venv/bin/python manage.py makemigrations

.PHONY: seed
seed: ## Load demo data
	cd $(BACKEND) && .venv/bin/python manage.py seed_demo

.PHONY: superuser
superuser: ## Create a superuser
	cd $(BACKEND) && .venv/bin/python manage.py createsuperuser

## --- run -----------------------------------------------------------------
.PHONY: run-backend
run-backend: ## Django dev server on :8000
	cd $(BACKEND) && .venv/bin/python manage.py runserver 0.0.0.0:8000

.PHONY: run-frontend
run-frontend: ## Vite dev server on :5173
	cd $(FRONTEND) && npm run dev

.PHONY: run-bot
run-bot: ## Telegram bot (long polling)
	cd $(BOT) && .venv/bin/python main.py

.PHONY: run-celery
run-celery: ## Celery worker
	cd $(BACKEND) && .venv/bin/celery -A config worker -l INFO

.PHONY: run-beat
run-beat: ## Celery beat scheduler
	cd $(BACKEND) && .venv/bin/celery -A config beat -l INFO --scheduler django_celery_beat.schedulers:DatabaseScheduler

## --- quality -------------------------------------------------------------
.PHONY: test
test: test-backend test-frontend ## Run every test suite

.PHONY: test-backend
test-backend: ## pytest
	cd $(BACKEND) && .venv/bin/python -m pytest

.PHONY: test-frontend
test-frontend: ## vitest
	cd $(FRONTEND) && npm run test

.PHONY: lint
lint: ## ruff + oxlint
	cd $(BACKEND) && .venv/bin/ruff check apps config tests
	cd $(FRONTEND) && npm run lint

.PHONY: check
check: ## Django system + migration checks and a frontend type-check/build
	cd $(BACKEND) && .venv/bin/python manage.py check
	cd $(BACKEND) && .venv/bin/python manage.py makemigrations --check --dry-run
	cd $(FRONTEND) && npm run build

.PHONY: build
build: ## Production frontend bundle
	cd $(FRONTEND) && npm run build

## --- docker --------------------------------------------------------------
.PHONY: up
up: ## docker compose up
	docker compose up -d --build

.PHONY: down
down: ## docker compose down
	docker compose down

.PHONY: logs
logs: ## Tail compose logs
	docker compose logs -f --tail=100
