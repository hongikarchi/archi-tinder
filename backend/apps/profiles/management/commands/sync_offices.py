from django.core.management.base import BaseCommand
from django.db import connections
from apps.profiles.models import Office


class Command(BaseCommand):
    help = 'Sync canonical_v2_architects (is_recommendable=true) into Office table'

    def handle(self, *args, **options):
        self.stdout.write('Fetching from buildings DB...')

        with connections['buildings'].cursor() as cur:
            cur.execute("""
                SELECT canonical_arch_id, canonical_name, description,
                       logo_url, primary_city, primary_country, website
                FROM canonical_v2_architects
                WHERE is_recommendable = true
            """)
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, row)) for row in cur.fetchall()]

        self.stdout.write(f'Found {len(rows)} recommendable architects. Upserting...')

        created = 0
        updated = 0
        skipped = 0
        for row in rows:
            arch_id = row['canonical_arch_id']
            defaults = {
                'name': row['canonical_name'] or '',
                'description': row['description'] or '',
                'logo_url': row['logo_url'] or '',
                'primary_city': row['primary_city'] or '',
                'primary_country': row['primary_country'] or '',
                'website': row['website'] or '',
                'is_recommendable': True,
            }
            # Guard against pre-existing duplicate rows (from interrupted prior runs).
            existing = Office.objects.filter(canonical_id=arch_id)
            count = existing.count()
            if count > 1:
                # Keep the oldest, update it, delete the rest.
                keep = existing.order_by('created_at').first()
                for field, value in defaults.items():
                    setattr(keep, field, value)
                keep.save(update_fields=list(defaults.keys()) + ['updated_at'])
                existing.exclude(office_id=keep.office_id).delete()
                updated += 1
                skipped += count - 1
            elif count == 1:
                obj = existing.first()
                for field, value in defaults.items():
                    setattr(obj, field, value)
                obj.save(update_fields=list(defaults.keys()) + ['updated_at'])
                updated += 1
            else:
                Office.objects.create(canonical_id=arch_id, **defaults)
                created += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Created: {created}, Updated: {updated}, '
            f'Duplicates removed: {skipped}, Total: {created + updated}'
        ))
