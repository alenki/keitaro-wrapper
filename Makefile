.PHONY: up down logs migrate test test-backend test-frontend lint format dev-backend dev-frontend

up: ## Build and start the app and the database
	docker compose up --build

down: ## Stop everything (data stays in the pgdata volume)
	docker compose down

logs: ## Follow the app logs
	docker compose logs -f app

migrate: ## Apply migrations by hand (the app also applies them on start)
	docker compose run --rm app alembic upgrade head

test: test-backend test-frontend ## All tests

test-backend: ## Backend tests against the Postgres from docker compose
	docker compose up -d --wait db
	cd backend && uv run pytest

test-frontend:
	cd frontend && npm test

lint: ## Linters and formatting checks, as in CI
	cd backend && uv run ruff check . && uv run ruff format --check .
	cd frontend && npm run lint && npm run format:check && npm run typecheck

format:
	cd backend && uv run ruff check --fix . && uv run ruff format .
	cd frontend && npm run format

dev-backend: ## API with reload on http://127.0.0.1:8000 (needs .env and the db service)
	docker compose up -d --wait db
	cd backend && uv run alembic upgrade head && uv run uvicorn app.main:create_app --factory --reload

dev-frontend: ## Vite dev server on http://127.0.0.1:5173, proxies /api to the backend
	cd frontend && npm run dev
