COMPOSE ?= docker compose
DOCKER ?= docker
DATABASE_URL ?= postgresql+psycopg://postgres:postgres@localhost:5432/workout_tracker
IMAGE ?= workout-tracker-mcp:local

.PHONY: up down logs status test docker-build ci

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

test:
	DATABASE_URL=$(DATABASE_URL) pytest

docker-build:
	$(DOCKER) build -t $(IMAGE) .

ci: test docker-build
