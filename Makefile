# ArchiTinder — Local Development Makefile

DEV_SUPERUSER_EMAIL   ?= admin@local.dev
DEV_SUPERUSER_PASSWORD ?= admin1234

BACKEND_DIR  = backend
FRONTEND_DIR = frontend

SHELL := /bin/bash

.PHONY: setup dev backend frontend reset-db dashboard migrate-local test-local

# ── Setup ────────────────────────────────────────────────────────────────────
setup:
	@echo "==> Installing backend dependencies..."
	cd $(BACKEND_DIR) && pip3 install -r requirements.txt
	@echo "==> Running migrations..."
	cd $(BACKEND_DIR) && python3 manage.py migrate
	@echo "==> Creating superuser (if not exists)..."
	cd $(BACKEND_DIR) && python3 manage.py shell -c \
		"from django.contrib.auth import get_user_model; U = get_user_model(); U.objects.filter(email='$(DEV_SUPERUSER_EMAIL)').exists() or U.objects.create_superuser('admin', '$(DEV_SUPERUSER_EMAIL)', '$(DEV_SUPERUSER_PASSWORD)')"
	@echo "==> Installing frontend dependencies..."
	cd $(FRONTEND_DIR) && npm install
	@echo "==> Setup complete."

# ── Dev (both servers) ───────────────────────────────────────────────────────
dev:
	@trap 'kill 0' INT TERM; \
	(cd $(BACKEND_DIR) && python3 manage.py runserver 8001) & \
	(cd $(FRONTEND_DIR) && npm run dev) & \
	wait

# ── Backend only ─────────────────────────────────────────────────────────────
backend:
	cd $(BACKEND_DIR) && python3 manage.py runserver 8001

# ── Frontend only ────────────────────────────────────────────────────────────
frontend:
	cd $(FRONTEND_DIR) && npm run dev

# ── Reset DB (migrations only, no wipe) ─────────────────────────────────────
reset-db:
	cd $(BACKEND_DIR) && python3 manage.py migrate

# ── Dashboard (open committed project state view) ──────────────────────────
dashboard:
	@command -v open >/dev/null 2>&1 && open project/dashboard.html || echo "Open project/dashboard.html in a browser."

# -- Local DB migrate (DDL via neondb_owner; prompts for pw, nothing persisted) --
# Local runtime user make_web_app has no DDL (INFRA-DB-1). Applies pending migrations
# to your LOCAL dev branch as neondb_owner, keeping DB_HOST/NAME from backend/.env so
# DDL hits LOCAL, never prod. Password is prompted (read -s), never written to disk.
# Runtime .env untouched. See memory project_local_db_migrate + CLAUDE.md INFRA-DB-1/ENV-1.
migrate-local:
	@cd $(BACKEND_DIR); \
	HOST=$$(grep -E '^DB_HOST=' .env | cut -d= -f2-); \
	NAME=$$(grep -E '^DB_NAME=' .env | cut -d= -f2-); \
	echo; echo "Pending migrations (as current runtime user):"; \
	python3 manage.py showmigrations 2>/dev/null | grep '\[ \]' || echo "  (none -- DB already current)"; \
	echo; echo "LOCAL migrate target  ->  HOST=$$HOST  NAME=$$NAME  USER=neondb_owner"; \
	echo "WARNING: runs DDL as neondb_owner. Confirm HOST above is your LOCAL dev branch, NOT production."; \
	read -p "Proceed? type 'yes': " ANS; \
	if [ "$$ANS" != "yes" ]; then echo "aborted."; exit 1; fi; \
	read -s -p "neondb_owner password: " PW; echo; \
	DB_USER=neondb_owner DB_PASSWORD="$$PW" python3 manage.py migrate && { echo; echo "Done. Runtime .env unchanged (still make_web_app)."; }

# -- Local pytest (CI-shape Postgres run; test DB via neondb_owner CREATEDB) ----
# Local runtime user make_web_app has no CREATEDB (INFRA-DB-1), so pytest-django
# cannot create its test database -> "permission denied to create database". This
# runs pytest as neondb_owner (which HAS CREATEDB), keeping DB_HOST/NAME from
# backend/.env so the throwaway test_<DB_NAME> lands on your LOCAL dev branch,
# NEVER prod. Password is prompted (read -s), never written to disk. Runtime .env
# is untouched. This is a CI-shape run against real Postgres+pgvector -- the
# conftest SQLite override is NOT load-bearing (see backend/conftest.py docstring).
# Pass pytest args via ARGS, e.g.  make test-local ARGS="-x -k liked_buildings"
# See memory project_local_db_migrate + CLAUDE.md INFRA-DB-1/ENV-1.
test-local:
	@cd $(BACKEND_DIR); \
	HOST=$$(grep -E '^DB_HOST=' .env | cut -d= -f2-); \
	NAME=$$(grep -E '^DB_NAME=' .env | cut -d= -f2-); \
	echo "LOCAL test DB target  ->  HOST=$$HOST  DB=test_$$NAME (created + dropped)  USER=neondb_owner"; \
	echo "WARNING: creates a throwaway test DB as neondb_owner. Confirm HOST above is your LOCAL dev branch, NOT production."; \
	read -p "Proceed? type 'yes': " ANS; \
	if [ "$$ANS" != "yes" ]; then echo "aborted."; exit 1; fi; \
	read -s -p "neondb_owner password: " PW; echo; \
	DB_USER=neondb_owner DB_PASSWORD="$$PW" python3 -m pytest $(ARGS)
