.PHONY: up down demo demo-local test screenshots install

up:
	docker compose up -d --build

down:
	docker compose down

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	.venv/bin/playwright install chromium

demo:
	docker compose exec -T app env PYTHONPATH=/app python /scripts/demo.py

demo-local:
	mkdir -p data
	SANDBOX_BASE_URL=http://127.0.0.1:8001 DATABASE_URL=sqlite:///./data/app.db PYTHONPATH=app python3 scripts/demo.py

test:
	PYTHONPATH=app pytest tests -q

screenshots:
	PYTHONPATH=app python3 scripts/capture_screenshots.py
