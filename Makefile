# Variables
UV_RUN = uv run
PYTHON_SCRIPT = PYTHONPATH=. $(UV_RUN) scripts/python
PYTEST = $(UV_RUN) python -m pytest

.PHONY: test-integration test-unit test-e2e test-e2e-clean test-all clean-db setup-db seed-db format lint check dash backfill

# Database management
clean-db:
	$(PYTHON_SCRIPT)/clean_test_db.py

setup-db:
	$(PYTHON_SCRIPT)/setup_test_db.py

seed-db:
	$(PYTHON_SCRIPT)/seed_test_data.py

# Test suites
test-unit:
	$(PYTEST) tests/unit/ -v

test-integration: clean-db setup-db seed-db
	@echo "🧪 Running integration tests..."
	$(PYTEST) tests/integration/test_database_integration.py -v

test-e2e:
	$(PYTHON_SCRIPT)/e2e_test_kraken.py

test-e2e-clean: clean-db setup-db seed-db test-e2e

test-all: test-unit test-integration test-e2e

# Development
format:
	$(UV_RUN) ruff check --fix .
	$(UV_RUN) ruff format .

lint:
	$(UV_RUN) ruff check .

check: lint

# Dashboard
dash:
	@echo "🚀 Starting Dash dashboard..."
	PYTHONPATH=. $(UV_RUN) python -c "from src.services.dash_service import DashService; DashService(debug=True).run()"

# Backfill historical data
backfill:
	$(PYTHON_SCRIPT)/kraken_backfill.py