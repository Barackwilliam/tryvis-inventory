"""
Create this project's Postgres schema before the first migrate.

The inventory system shares a Supabase instance with the tryvis.co.tz website.
Keeping it in its own schema is what lets both projects own a table called
django_migrations, or auth_user, without one standing on the other.

    python manage.py init_schema

This command only creates the schema. It deliberately does NOT touch the
database role: on Supabase both projects usually sign in as the same
"postgres" user, so an ALTER ROLE ... SET search_path here would follow the
website's connections too and hide its own tables from it. The schema this
project uses is set per connection, in DATABASES["default"]["OPTIONS"].
"""
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Create the project's Postgres schema if it does not exist."

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING(
                f"Database is {connection.vendor}, not postgresql - nothing to do."
            ))
            return

        schema = settings.DB_SCHEMA

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = %s)",
                [schema],
            )
            existed = cursor.fetchone()[0]
            cursor.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')

        # The connection was opened with a search_path pointing at a schema that
        # did not exist yet, so current_schema() is still NULL on it. Reconnect.
        connection.close()

        with connection.cursor() as cursor:
            cursor.execute("SELECT current_schema(), current_user")
            current, user = cursor.fetchone()

        if existed:
            self.stdout.write(f'Schema "{schema}" was already there.')
        else:
            self.stdout.write(self.style.SUCCESS(f'Schema "{schema}" created.'))

        if current == schema:
            self.stdout.write(self.style.SUCCESS(
                f'Connected as "{user}", working in "{current}". Ready to migrate.'
            ))
        else:
            self.stdout.write(self.style.ERROR(
                f'Expected to be in "{schema}" but current_schema() says "{current}". '
                "Check DB_SCHEMA and the OPTIONS search_path in settings before migrating."
            ))
