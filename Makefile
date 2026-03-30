# ArchiTinder — Local Development Makefile

DEV_SUPERUSER_EMAIL   ?= admin@local.dev
DEV_SUPERUSER_PASSWORD ?= admin1234

BACKEND_DIR  = backend
FRONTEND_DIR = frontend

.PHONY: setup dev backend frontend reset-db

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
