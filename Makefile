.PHONY: seed run api

# Seed the ChromaDB with incidents
seed:
	ethicsbot seed --file data/incidents/seed_incidents.jsonl

# Start the FastAPI server
api:
	uvicorn ethics_engine.api.main:app --reload --host 0.0.0.0 --port 8000

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