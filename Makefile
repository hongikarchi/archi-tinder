# ArchiTinder — Local Development Makefile

DEV_SUPERUSER_EMAIL   ?= admin@local.dev
DEV_SUPERUSER_PASSWORD ?= admin1234

BACKEND_DIR  = backend
FRONTEND_DIR = frontend

SHELL := /bin/bash

.PHONY: setup dev backend frontend reset-db dashboard migrate-local test-local migrate-prod

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

# -- Prod DB migrate (post-deploy step; DDL via neondb_owner) -------------------
# Prod runtime user make_web_app has no DDL (INFRA-DB-1), so Railway can NOT
# auto-migrate on deploy -- pending migrations are applied manually AFTER Railway
# finishes deploying the new code (code-first ordering; see CONTRIBUTING.md
# "Deploy runbook"). Credentials come from backend/.env.prod.owner (gitignored,
# chmod 600; DB_HOST = the PRODUCTION Neon endpoint, DB_USER = neondb_owner).
# Runtime .env is untouched -- DB_* are injected inline for this command only
# (settings.py load_dotenv override=False, so inline env wins). Pending
# migrations containing destructive/data ops are flagged before the confirm.
migrate-prod:
	@cd $(BACKEND_DIR); \
	if [ ! -f .env.prod.owner ]; then \
		echo "ERROR: backend/.env.prod.owner missing."; \
		echo "Create it (gitignored, chmod 600) with the PROD endpoint + neondb_owner:"; \
		echo "  DB_HOST=<prod neon endpoint>"; \
		echo "  DB_PORT=5432"; \
		echo "  DB_NAME=user_data"; \
		echo "  DB_USER=neondb_owner"; \
		echo "  DB_PASSWORD=<neondb_owner password>"; \
		exit 1; fi; \
	HOST=$$(grep -E '^DB_HOST=' .env.prod.owner | cut -d= -f2-); \
	PORT=$$(grep -E '^DB_PORT=' .env.prod.owner | cut -d= -f2-); \
	NAME=$$(grep -E '^DB_NAME=' .env.prod.owner | cut -d= -f2-); \
	DBUSER=$$(grep -E '^DB_USER=' .env.prod.owner | cut -d= -f2-); \
	PW=$$(grep -E '^DB_PASSWORD=' .env.prod.owner | cut -d= -f2-); \
	echo; echo "PROD migrate target  ->  HOST=$$HOST  NAME=$$NAME  USER=$$DBUSER"; \
	echo; echo "Pending migrations on PROD:"; \
	PENDING=$$(DB_HOST="$$HOST" DB_PORT="$$PORT" DB_NAME="$$NAME" DB_USER="$$DBUSER" DB_PASSWORD="$$PW" python3 manage.py showmigrations 2>/dev/null | grep '\[ \]' || true); \
	if [ -z "$$PENDING" ]; then echo "  (none -- prod already current)"; exit 0; fi; \
	echo "$$PENDING"; \
	DESTR=""; \
	for MIG in $$(echo "$$PENDING" | sed 's/.*\[ \] //'); do \
		F=$$(find . -path "*/migrations/$$MIG.py" 2>/dev/null | head -1); \
		if [ -n "$$F" ] && grep -qE 'RemoveField|DeleteModel|RenameField|RenameModel|RunSQL|RunPython' "$$F"; then DESTR="$$DESTR $$MIG"; fi; \
	done; \
	if [ -n "$$DESTR" ]; then \
		echo; echo "!! DESTRUCTIVE/data ops detected in:$$DESTR"; \
		echo "!! Column/table drops crash OLD code still running. Confirm Railway finished"; \
		echo "!! deploying the NEW code before applying (code-first ordering)."; \
	fi; \
	echo; echo "ORDER CHECK: run this only AFTER the Railway deploy for this release is live."; \
	read -p "Apply to PRODUCTION? type 'deploy-prod': " ANS; \
	if [ "$$ANS" != "deploy-prod" ]; then echo "aborted."; exit 1; fi; \
	DB_HOST="$$HOST" DB_PORT="$$PORT" DB_NAME="$$NAME" DB_USER="$$DBUSER" DB_PASSWORD="$$PW" python3 manage.py migrate && { echo; echo "Done. Prod schema current. Runtime .env unchanged (still make_web_app)."; }

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
	PORT=$$(grep -E '^DB_PORT=' .env | cut -d= -f2-); \
	echo "LOCAL test DB target  ->  HOST=$$HOST  DB=test_$$NAME (created + dropped)  USER=neondb_owner"; \
	echo "WARNING: creates a throwaway test DB as neondb_owner. Confirm HOST above is your LOCAL dev branch, NOT production."; \
	read -p "Proceed? type 'yes': " ANS; \
	if [ "$$ANS" != "yes" ]; then echo "aborted."; exit 1; fi; \
	read -s -p "neondb_owner password: " PW; echo; \
	DB_HOST="$$HOST" DB_NAME="$$NAME" DB_PORT="$$PORT" DB_USER=neondb_owner DB_PASSWORD="$$PW" python3 -m pytest $(ARGS)
