.PHONY: install demo fetch api frontend test

install:
	pip install -r requirements.txt
	@echo "✅ Backend installed."
	@echo "   For frontend: cd frontend && npm install"

demo:
	python scripts/demo_simulation.py --sims 3000

demo-monaco:
	python scripts/demo_simulation.py --circuit monaco --sims 3000

fetch:
	python scripts/fetch_data.py --year 2024

api:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

frontend:
	cd frontend && npm run dev -- --host 0.0.0.0 --port 5173

test:
	pytest -q

docker-up:
	docker-compose up --build

docker-down:
	docker-compose down
