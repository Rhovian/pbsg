# Available targets:
#   test-integration  - Clean database, setup schema, seed data, run integration tests
#   test-unit        - Run unit tests only
#   test-e2e         - Run end-to-end test with live Kraken websocket
#   test-e2e-clean   - Run e2e test with fresh database setup
#   test-all         - Run all tests (unit + integration + e2e)
#   clean-db         - Clean database (drop all tables)
#   setup-db         - Setup database schema and hypertables
#   seed-db          - Seed database with test data
#   format           - Format Python code with black

.PHONY: test-integration test-unit test-e2e test-e2e-clean test-all clean-db setup-db seed-db format

# Run full integration test suite: clean -> setup -> seed -> test
test-integration:
	@echo "🧹 Cleaning database..."
	uv run scripts/clean_test_db.py
	@echo "📊 Setting up database schema..."
	uv run scripts/setup_test_db.py
	@echo "🌱 Seeding test data..."
	uv run scripts/seed_test_data.py
	@echo "🧪 Running integration tests..."
	uv run python -m pytest tests/integration/test_database_integration.py -v

# Individual commands
clean-db:
	uv run python scripts/clean_test_db.py

setup-db:
	uv run python scripts/setup_test_db.py

seed-db:
	uv run python scripts/seed_test_data.py

# Run unit tests
test-unit:
	uv run python -m pytest tests/unit/ -v

# Run end-to-end test with live Kraken data
test-e2e:
	@echo "🌐 Running e2e test with live Kraken websocket..."
	uv run scripts/e2e_test_kraken.py

# Run e2e test with fresh database setup
test-e2e-clean: clean-db setup-db seed-db
	@echo "🌐 Running e2e test with fresh database..."
	uv run scripts/e2e_test_kraken.py

# Run all tests
test-all: test-unit test-integration test-e2e

# Format Python code with black
format:
	@echo "🎨 Formatting Python code with black..."
	uv run black .