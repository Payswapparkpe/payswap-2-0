"""Terminate idle PostgreSQL sessions for the app database user."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Terminate idle PostgreSQL connections for the configured DB user."

    def handle(self, *args, **options):
        engine = settings.DATABASES["default"]["ENGINE"]
        if "postgresql" not in engine:
            self.stdout.write("Default database is not PostgreSQL; nothing to do.")
            return

        db_user = settings.DATABASES["default"]["USER"]
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_terminate_backend(pid)
                FROM pg_stat_activity
                WHERE usename = %s
                  AND datname = current_database()
                  AND state = 'idle'
                  AND pid <> pg_backend_pid()
                """,
                [db_user],
            )
            terminated = cursor.rowcount
        self.stdout.write(self.style.SUCCESS(f"Terminated {terminated} idle connection(s) for {db_user}."))
