.PHONY: dev up down seed test demo fixtures

up:
	docker compose up --build

down:
	docker compose down -v

dev:
	docker compose up -d falkordb
	cd backend && python -m blackbox.seed --all && uvicorn blackbox.api:app --reload --port 8000

seed:
	cd backend && python -m blackbox.seed --all

test:
	cd backend && python -m pytest -q

demo:
	cd backend && python -m blackbox.run_demo

fixtures:
	cd backend && python -m blackbox.record_fixtures
