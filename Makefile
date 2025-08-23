# ---- Variables ----
PORT ?= 7860
APP  := ethics_engine.ui.app

# ---- Targets ----
.PHONY: seed run api watch watch-fast run-fast ui dev-ui test test-cov fmt lint clean

# Seed the ChromaDB with incidents
seed:
	ethicsbot seed --file data/incidents/seed_incidents.jsonl

# Start the FastAPI server
api:
	uvicorn ethics_engine.api.main:app --reload --host 0.0.0.0 --port 8000

ui:
	uv run python -m $(APP)

ui-watch:
	uv run watchmedo auto-restart \
	  --directory=ethics_engine \
	  --pattern="*.py" \
	  --recursive \
	  -- uv run python -m $(APP)

test:
	uv run pytest

test-cov:
	uv run pytest --cov=ethics_engine --cov-report=term-missing

fmt:
	uv run ruff format .
	uv run ruff check . --fix

lint:
	uv run ruff check .

clean:
	rm -rf .pytest_cache .ruff_cache .mypy_cache dist build *.egg-info

# Run a quick CLI analysis
run:
	ethicsbot run --q "AI for job screening using resumes"

# Same, but forces a smaller model for quick iterations
run-fast:
	ethicsbot run --q "AI for job screening using resumes" --model llama3.2

watch:
	ethicsbot watch --text "BREAKING: Secret plan exposed! A new AI will fire all nurses by next week without notice." --k 3

watch-fast:
	ethicsbot watch --text "BREAKING: Secret plan exposed! A new AI will fire all nurses by next week without notice." --k 3 --model llama3.2