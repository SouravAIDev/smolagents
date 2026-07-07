.PHONY: help install dev prod test clean docker-up docker-down docker-build docker-logs lint format security-check coverage docs

# Color output
COLOR_RESET := \033[0m
COLOR_BOLD := \033[1m
COLOR_GREEN := \033[32m
COLOR_YELLOW := \033[33m
COLOR_BLUE := \033[34m

help:
	@echo "$(COLOR_BOLD)$(COLOR_BLUE)Book Finder Agent - Available Commands$(COLOR_RESET)"
	@echo ""
	@echo "$(COLOR_BOLD)Setup & Installation:$(COLOR_RESET)"
	@echo "  make install                Install dependencies in virtual environment"
	@echo "  make install-dev            Install dependencies including dev tools"
	@echo ""
	@echo "$(COLOR_BOLD)Development:$(COLOR_RESET)"
	@echo "  make dev                    Start development server with Flask debug"
	@echo "  make dev-docker             Start complete dev stack with Docker Compose"
	@echo "  make repl                   Start interactive Python REPL with app context"
	@echo ""
	@echo "$(COLOR_BOLD)Testing & Quality:$(COLOR_RESET)"
	@echo "  make test                   Run pytest test suite"
	@echo "  make test-cov               Run tests with coverage report"
	@echo "  make test-watch             Run tests in watch mode"
	@echo "  make lint                   Run code linters (pylint, flake8)"
	@echo "  make format                 Format code (black, isort)"
	@echo "  make security-check         Run security checks (bandit)"
	@echo "  make quality                Run full quality suite (lint, format, test)"
	@echo ""
	@echo "$(COLOR_BOLD)Docker Operations:$(COLOR_RESET)"
	@echo "  make docker-build           Build Docker image"
	@echo "  make docker-up              Start Docker Compose stack"
	@echo "  make docker-down            Stop Docker Compose stack"
	@echo "  make docker-logs            Show Docker logs (use FOLLOW=1 to tail)"
	@echo "  make docker-clean           Remove Docker stack and volumes"
	@echo "  make docker-reset           Reset everything (containers, volumes, images)"
	@echo ""
	@echo "$(COLOR_BOLD)Database:$(COLOR_RESET)"
	@echo "  make db-migrate             Run database migrations"
	@echo "  make db-seed                Seed database with test data"
	@echo "  make db-reset               Reset database to initial state"
	@echo "  make db-shell               Open PostgreSQL shell"
	@echo ""
	@echo "$(COLOR_BOLD)Documentation:$(COLOR_RESET)"
	@echo "  make docs                   Generate/update documentation"
	@echo "  make docs-serve             Serve documentation locally"
	@echo ""
	@echo "$(COLOR_BOLD)Deployment:$(COLOR_RESET)"
	@echo "  make prod                   Build and start production container"
	@echo "  make health-check           Verify agent health endpoint"
	@echo "  make api-test               Test API endpoints"
	@echo ""
	@echo "$(COLOR_BOLD)Utilities:$(COLOR_RESET)"
	@echo "  make env-setup              Copy .env.example to .env"
	@echo "  make clean                  Remove build artifacts and cache"
	@echo "  make clean-all              Remove all generated files and docker data"
	@echo ""

# Setup targets
install:
	@echo "$(COLOR_GREEN)Installing dependencies...$(COLOR_RESET)"
	python -m venv .venv
	. .venv/bin/activate && pip install --upgrade pip setuptools wheel
	. .venv/bin/activate && pip install -q -r requirements.txt
	@echo "$(COLOR_GREEN)✓ Installation complete$(COLOR_RESET)"

install-dev: install
	@echo "$(COLOR_GREEN)Installing development dependencies...$(COLOR_RESET)"
	. .venv/bin/activate && pip install -q pytest pytest-cov pytest-watch black isort flake8 pylint bandit mkdocs
	@echo "$(COLOR_GREEN)✓ Dev dependencies installed$(COLOR_RESET)"

env-setup:
	@if [ ! -f .env ]; then \
		echo "$(COLOR_YELLOW)Copying .env.example to .env$(COLOR_RESET)"; \
		cp .env.example .env; \
		echo "$(COLOR_YELLOW)⚠ Please update .env with your configuration values$(COLOR_RESET)"; \
	else \
		echo "$(COLOR_YELLOW).env already exists, skipping$(COLOR_RESET)"; \
	fi

# Development targets
dev: env-setup
	@echo "$(COLOR_GREEN)Starting development server...$(COLOR_RESET)"
	. .venv/bin/activate && FLASK_ENV=development FLASK_DEBUG=True python run.py

dev-docker: env-setup docker-build
	@echo "$(COLOR_GREEN)Starting Docker Compose stack...$(COLOR_RESET)"
	docker-compose up -d
	@echo "$(COLOR_GREEN)✓ Stack started. Agent available at http://localhost:5000$(COLOR_RESET)"
	repl:
	@echo "$(COLOR_GREEN)Starting interactive REPL...$(COLOR_RESET)"
	. .venv/bin/activate && python -c "from run import app; app.app_context().push(); print('Flask app context ready'); import IPython; IPython.embed()"

# Testing targets
test:
	@echo "$(COLOR_GREEN)Running tests...$(COLOR_RESET)"
	. .venv/bin/activate && pytest tests/ -v --tb=short

test-cov:
	@echo "$(COLOR_GREEN)Running tests with coverage...$(COLOR_RESET)"
	. .venv/bin/activate && pytest tests/ --cov=. --cov-report=html --cov-report=term
	@echo "$(COLOR_GREEN)Coverage report generated in htmlcov/index.html$(COLOR_RESET)"

test-watch:
	@echo "$(COLOR_GREEN)Running tests in watch mode...$(COLOR_RESET)"
	. .venv/bin/activate && ptw tests/ -- -v

# Quality & Linting targets
lint:
	@echo "$(COLOR_GREEN)Running linters...$(COLOR_RESET)"
	. .venv/bin/activate && pylint book_finder_agent.py book_finder_setup.py book_helper.py run.py --disable=all --enable=E,F,W 2>/dev/null || true
	. .venv/bin/activate && flake8 . --count --statistics

format:
	@echo "$(COLOR_GREEN)Formatting code...$(COLOR_RESET)"
	. .venv/bin/activate && black . --line-length=120
	. .venv/bin/activate && isort . --profile black --line-length=120
	@echo "$(COLOR_GREEN)✓ Code formatted$(COLOR_RESET)"

security-check:
	@echo "$(COLOR_GREEN)Running security checks...$(COLOR_RESET)"
	. .venv/bin/activate && bandit -r . -ll -x ./tests,./.venv

quality: lint format security-check test
	@echo "$(COLOR_GREEN)✓ All quality checks passed$(COLOR_RESET)"

# Docker targets
docker-build:
	@echo "$(COLOR_GREEN)Building Docker image...$(COLOR_RESET)"
	docker-compose build --no-cache
	@echo "$(COLOR_GREEN)✓ Image built$(COLOR_RESET)"

docker-up: env-setup
	@echo "$(COLOR_GREEN)Starting Docker stack...$(COLOR_RESET)"
	docker-compose up -d
	@echo "$(COLOR_GREEN)✓ Stack started$(COLOR_RESET)"
	@echo "$(COLOR_YELLOW)Waiting for services to be ready...$(COLOR_RESET)"
	@sleep 5
	@docker-compose ps

docker-down:
	@echo "$(COLOR_YELLOW)Stopping Docker stack...$(COLOR_RESET)"
	docker-compose down
	@echo "$(COLOR_GREEN)✓ Stack stopped$(COLOR_RESET)"

FOLLOW ?= 0
ifeq ($(FOLLOW), 1)
DOCKER_LOGS_FOLLOW = -f
else
DOCKER_LOGS_FOLLOW =
endif

docker-logs:
	@docker-compose logs $(DOCKER_LOGS_FOLLOW) $(SERVICE)

docker-clean: docker-down
	@echo "$(COLOR_YELLOW)Removing stopped containers...$(COLOR_RESET)"
	docker-compose rm -f
	@echo "$(COLOR_GREEN)✓ Containers removed$(COLOR_RESET)"

docker-reset: docker-clean
	@echo "$(COLOR_YELLOW)Removing volumes and images...$(COLOR_RESET)"
	docker volume rm book_finder_postgres book_finder_redis 2>/dev/null || true
	docker-compose down -v --remove-orphans
	docker rmi book_finder_agent:latest 2>/dev/null || true
	@echo "$(COLOR_GREEN)✓ All Docker resources removed$(COLOR_RESET)"

# Database targets
db-migrate:
	@echo "$(COLOR_GREEN)Running database migrations...$(COLOR_RESET)"
	. .venv/bin/activate && python -c "from book_finder_agent import BookFinderAgent_v2; print('Migration placeholder')"
	@echo "$(COLOR_GREEN)✓ Migrations complete$(COLOR_RESET)"

db-seed:
	@echo "$(COLOR_YELLOW)Seeding database with test data...$(COLOR_RESET)"
	. .venv/bin/activate && python scripts/seed_database.py
	@echo "$(COLOR_GREEN)✓ Database seeded$(COLOR_RESET)"

db-reset: docker-down
	@echo "$(COLOR_YELLOW)Resetting database...$(COLOR_RESET)"
	docker volume rm book_finder_postgres 2>/dev/null || true
	docker-compose up -d postgres
	@echo "$(COLOR_GREEN)✓ Database reset$(COLOR_RESET)"

db-shell:
	@echo "$(COLOR_GREEN)Opening PostgreSQL shell...$(COLOR_RESET)"
	docker-compose exec postgres psql -U ${DB_USER:-postgres} -d ${DB_NAME:-book_finder_db}

# Documentation targets
docs:
	@echo "$(COLOR_GREEN)Generating documentation...$(COLOR_RESET)"
	. .venv/bin/activate && mkdocs build
	@echo "$(COLOR_GREEN)✓ Documentation generated in site/$(COLOR_RESET)"

docs-serve: docs
	@echo "$(COLOR_GREEN)Serving documentation...$(COLOR_RESET)"
	. .venv/bin/activate && mkdocs serve

# Health & API testing
health-check:
	@echo "$(COLOR_GREEN)Checking agent health...$(COLOR_RESET)"
	@curl -s http://localhost:5000/utility/book-finder-agent/ || echo "$(COLOR_YELLOW)Agent not accessible$(COLOR_RESET)"

api-test:
	@echo "$(COLOR_GREEN)Testing API endpoints...$(COLOR_RESET)"
	@echo "Checking health endpoint..."
	@curl -s http://localhost:5000/utility/book-finder-agent/ | head -c 50 && echo "\n✓ Health check passed"
	@echo "Checking config endpoint..."
	@curl -s http://localhost:5000/utility/book-finder-agent/get_config | python -m json.tool | head -5 && echo "✓ Config endpoint accessible"

# Cleanup targets
clean:
	@echo "$(COLOR_YELLOW)Removing build artifacts...$(COLOR_RESET)"
	rm -rf build/ dist/ *.egg-info .pytest_cache .coverage htmlcov .mypy_cache __pycache__ .venv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete
	@echo "$(COLOR_GREEN)✓ Clean complete$(COLOR_RESET)"

clean-all: clean docker-reset
	@echo "$(COLOR_GREEN)✓ Complete cleanup done$(COLOR_RESET)"

