# Hyperliquid Trading Test Makefile

.PHONY: test test-unit test-integration test-compatibility test-smoke help install-test-deps

# Default target
help:
	@echo "Available test targets:"
	@echo "  test              - Run all tests"
	@echo "  test-unit         - Run unit tests only (fast)"
	@echo "  test-integration  - Run integration tests only (requires .env)"
	@echo "  test-compatibility- Run compatibility tests only"
	@echo "  test-smoke        - Run smoke tests only"
	@echo "  install-test-deps - Install testing dependencies"
	@echo "  clean-test        - Clean test artifacts"

# Install testing dependencies
install-test-deps:
	pip install pytest pytest-mock pytest-cov

# Run all tests
test:
	python run_tests.py --all

# Run unit tests (fast, no network)
test-unit:
	python run_tests.py --unit

# Run integration tests (requires network and .env)
test-integration:
	python run_tests.py --integration

# Run compatibility tests
test-compatibility:
	python run_tests.py --compatibility

# Run smoke tests
test-smoke:
	python run_tests.py --smoke

# Alternative pytest commands
pytest-unit:
	pytest tests/unit/ -v

pytest-integration:
	pytest tests/integration/ -v -m integration

pytest-all:
	pytest tests/ -v

# Clean test artifacts
clean-test:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# Run tests with coverage
test-coverage:
	pytest tests/ --cov=src/hyperliq --cov-report=html --cov-report=term

# Check test structure
test-structure:
	@echo "Test directory structure:"
	@find tests/ -name "*.py" | sort