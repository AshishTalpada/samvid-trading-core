# Samvid Trading Core - Developer Interface

.PHONY: dev test lint docker-up setup

# Start the full development stack
dev:
	@echo "🚀 Starting Samvid Backend..."
	python src/main.py &
	@echo "⚛️ Starting React Dashboard..."
	cd frontend && npm run dev

# Run the test suite
test:
	pytest tests/

# Run quality checks (ruff & mypy)
lint:
	ruff check src/
	mypy src/

# Spin up localized infrastructure (QuestDB)
docker-up:
	docker-compose -f docker-compose.questdb.yml up -d

# Initialize the local environment
setup:
	pip install -r requirements.txt
	cd frontend && npm install
	python vault_setup.py
