.PHONY: up down dev logs test test-unit test-integration test-e2e eval build clean help

# Default target
help:
	@echo "HR Assistant — Available Commands"
	@echo ""
	@echo "  make up           Start all services (production mode)"
	@echo "  make dev          Start with hot-reload (development mode)"
	@echo "  make down         Stop all services"
	@echo "  make logs         Tail all logs"
	@echo "  make build        Rebuild all Docker images"
	@echo ""
	@echo "  make test         Run unit tests"
	@echo "  make test-all     Run all test tiers"
	@echo "  make eval         Run RAG evaluation"
	@echo ""
	@echo "  make clean        Remove containers, volumes, and build cache"
	@echo "  make seed         Re-run database seed"
	@echo ""

up:
	docker compose up -d
	@echo ""
	@echo "✅ Started. Open http://localhost"
	@echo "   Demo login: ahmed@company.sa / demo1234"

dev:
	docker compose -f docker-compose.yml -f docker-compose.override.yml up

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

build:
	docker compose build --no-cache

test:
	cd backend && python -m pytest tests/unit/ -v --tb=short

test-integration:
	cd backend && python -m pytest tests/integration/ -v --tb=short

test-e2e:
	cd backend && python -m pytest tests/e2e/ -v -s --timeout=120

test-all:
	./scripts/run_tests.sh all

eval:
	python evaluation/run_eval.py

seed:
	docker compose exec postgres psql -U hruser -d hrdb -f /docker-entrypoint-initdb.d/init.sql

clean:
	docker compose down -v --remove-orphans
	docker system prune -f

# Quick sanity check — curl the health endpoint
health:
	@curl -sf http://localhost/health && echo " Backend OK" || echo " Backend not responding"
	@curl -sf http://localhost/ > /dev/null && echo " Frontend OK" || echo " Frontend not responding"
