"""
0018 -- Rename SwipeEvent.building_id -> SwipeEvent.canonical_bld_id (S2 v2 schema).

Background:
    Make DB replaced `architecture_vectors` (PK=`building_id` like 'B00042') with
    `canonical_v2_buildings` (PK=`canonical_bld_id` like 'bld_000344'). Make Web
    now stores the new canonical ID on every SwipeEvent for consistency with the
    upstream PK and the new card-dict / API contract.

Migration semantics:
    Field-rename only (no data transform). The column previously held v1 IDs;
    after the v2 cutover, all new rows carry v2 IDs. Historical rows are left
    in place with their old v1 string values — they become orphans (no longer
    join to canonical_v2_buildings). This is acceptable per the S2 plan: liked /
    swiped data from the v1 corpus does not map cleanly to v2.

Reversible (down migration is a no-op rename).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('recommendation', '0017_add_extended_rounds'),
    ]

    operations = [
        migrations.RenameField(
            model_name='swipeevent',
            old_name='building_id',
            new_name='canonical_bld_id',
        ),
    ]
