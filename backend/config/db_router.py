"""
db_router.py -- Django multi-database router for Make Web.

Phase A (behavior-neutral): 'buildings' alias points at the same Neon DB as
'default'.  Phase B will provision a real read-replica and flip BUILDINGS_DB_*
env vars.

Routing logic:
  - db_for_read / db_for_write / allow_relation: return None (defer to default
    Django behavior -- every ORM model lives on 'default').
  - allow_migrate: block migration attempts on 'buildings' (canonical_v2_buildings
    is owned by Make DB; Make Web must never migrate it).
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
