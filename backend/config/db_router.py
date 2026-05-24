"""
db_router.py -- Django multi-database router for Make Web.

Two-database topology on a single Neon endpoint:
  - 'default' alias -> user_data DB (Make Web ORM target; auth, profiles,
    recommendation, etc.).
  - 'buildings' alias -> archi_data DB (Make-DB-owned, read-only). Make Web
    queries `canonical_v2_buildings` + `canonical_v2_architects` via raw SQL
    using a dedicated SELECT-only role (`make_web`).

Routing logic:
  - db_for_read / db_for_write / allow_relation: return None (defer to default
    Django behavior -- every ORM model lives on 'default').
  - allow_migrate: block migration attempts on 'buildings' (archi_data is
    owned by Make DB; Make Web must never migrate it).
"""


class MakeWebRouter:
    """Route building-data read connections; block migrations on 'buildings'."""

    def db_for_read(self, model, **hints):
        # ORM models all live on 'default'; raw SQL callers select 'buildings'
        # explicitly via connections['buildings'].cursor().
        return None

    def db_for_write(self, model, **hints):
        return None

    def allow_relation(self, obj1, obj2, **hints):
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db == 'buildings':
            return False
        return None
