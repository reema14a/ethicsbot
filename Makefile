.PHONY: seed run api

# Seed the ChromaDB with incidents
seed:
	ethicsbot seed --file data/incidents/seed_incidents.jsonl

# Run a quick CLI analysis
run:
	ethicsbot run --q "AI for job screening using resumes"

# Same, but forces a smaller model for quick iterations
run-fast:
	ethicsbot run --q "AI for job screening using resumes" --model llama3.2

# Start the FastAPI server
api:
	uvicorn ethics_engine.api.main:app --reload --host 0.0.0.0 --port 8000
