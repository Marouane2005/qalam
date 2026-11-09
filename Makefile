.PHONY: up down logs test lint web seed

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

test:
	cd api && pytest

lint:
	cd api && ruff check . && mypy --package qalam
	cd web && npm run lint && npm run typecheck

web:
	cd web && npm run build

seed:
	docker compose exec api python -m qalam.cli seed
