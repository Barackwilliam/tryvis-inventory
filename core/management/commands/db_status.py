"""
Show exactly which schema this project is talking to.

    python manage.py db_status

Run it before the first migrate, and any time migrations behave strangely.
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Report the active schema, search path and where tables actually live."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING(f"Database is {connection.vendor}."))
            return

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_database(), current_user, current_schema()")
            database, user, schema = cursor.fetchone()
            cursor.execute("SHOW search_path")
            search_path = cursor.fetchone()[0]
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                [settings.DB_SCHEMA],
            )
            schema_exists = cursor.fetchone()[0]

            self.stdout.write(f"Database      : {database}")
            self.stdout.write(f"User          : {user}")
            self.stdout.write(f"Search path   : {search_path}")
            self.stdout.write(f"Current schema: {schema}")
            self.stdout.write(
                f'Schema "{settings.DB_SCHEMA}" exists: '
                + ("yes" if schema_exists else self.style.ERROR("NO"))
            )

            if schema != settings.DB_SCHEMA:
                self.stdout.write(self.style.ERROR(
                    f'\nSTOP. Django is pointed at "{schema}", not "{settings.DB_SCHEMA}". '
                    "Run init_schema before migrating, or you will write into the "
                    "website's schema."
                ))

            self.stdout.write("\nMigration tables found:")
            cursor.execute("""
                SELECT table_schema, COUNT(*)
                FROM information_schema.tables
                WHERE table_name = 'django_migrations'
                GROUP BY table_schema ORDER BY table_schema
            """)
            rows = cursor.fetchall()
            if not rows:
                self.stdout.write("  none yet")
            for table_schema, _ in rows:
                cursor.execute(
                    f'SELECT COUNT(*), COUNT(DISTINCT app) FROM "{table_schema}".django_migrations'
                )
                applied, apps = cursor.fetchone()
                marker = "  <- this project" if table_schema == settings.DB_SCHEMA else ""
                self.stdout.write(f"  {table_schema}: {applied} applied across {apps} app(s){marker}")

            self.stdout.write("\nTables per schema:")
            cursor.execute("""
                SELECT table_schema, COUNT(*)
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                GROUP BY table_schema ORDER BY table_schema
            """)
            for table_schema, count in cursor.fetchall():
                self.stdout.write(f"  {table_schema}: {count}")
