.PHONY: up down simulator integration-test clean help

help:
	@echo "Available commands:"
	@echo "  make up               - Build and start all Docker containers in background"
	@echo "  make down             - Stop and remove all containers, networks, and volumes"
	@echo "  make simulator        - Run the local sensor simulator script"
	@echo "  make integration-test - Run the integration test suite using pytest"
	@echo "  make clean            - Remove python cache and temp files"

up:
	docker compose up --build -d

down:
	docker compose down -v

simulator:
	python scripts/sensor_simulator.py

integration-test:
	pytest tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "*.egg-info" -exec rm -rf {} +
