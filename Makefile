SHELL := /bin/bash
COMPOSE ?= docker compose
DOCKER ?= docker
POSTGRES_USER ?= postgres
POSTGRES_PASSWORD ?= postgres
POSTGRES_DB ?= workout_tracker
DATABASE_URL ?= postgresql+psycopg://$(POSTGRES_USER):$(POSTGRES_PASSWORD)@localhost:5432/$(POSTGRES_DB)
IMAGE ?= workout-tracker-mcp:local

.PHONY: up down logs status db-up db-down db-wait test test-only services-up services-down docker-build ci

up:
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f

status:
	$(COMPOSE) ps

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) down

db-wait:
	$(COMPOSE) exec -T postgres sh -c "until pg_isready -U $$POSTGRES_USER -d $$POSTGRES_DB; do sleep 1; done"

test: db-up db-wait
	DATABASE_URL=$(DATABASE_URL) pytest

test-only:
	DATABASE_URL=$(DATABASE_URL) pytest

services-up: db-up

services-down: db-down

docker-build:
	$(DOCKER) build -t $(IMAGE) .

ci:
	@set -euo pipefail; \
	trap '$(MAKE) db-down' EXIT; \
	$(MAKE) db-up; \
	$(MAKE) db-wait; \
	DATABASE_URL=$(DATABASE_URL) pytest; \
	$(DOCKER) build -t $(IMAGE) .
