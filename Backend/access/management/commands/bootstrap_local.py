from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from access.models import Department
from access.policy import Policy


class Command(BaseCommand):
    help = "Seed catalog/roles and create local portal users if they do not exist."

    def add_arguments(self, parser):
        parser.add_argument("--password", help="Password to set for newly created local users.")

    def handle(self, *args, **options):
        password = options.get("password")
        if not password:
            raise CommandError("Pass --password to create local portal users.")
        call_command("seed_payswaphub")
        User = get_user_model()
        specs = [
            ("admin@payswap.local", "ADMIN", "platform_admin", None),
            ("kyc@payswap.local", "EMPLOYEE", "kyc", "kyc"),
            ("ops@payswap.local", "EMPLOYEE", "operations", "operations"),
            ("merchant@payswap.local", "MERCHANT", "merchant", None),
        ]
        for email, user_type, role, dept_slug in specs:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"user_type": user_type, "name": email.split("@")[0]},
            )
            if created:
                user.set_password(password)
                if user_type == "ADMIN":
                    user.is_staff = True
                if dept_slug:
                    user.department = Department.objects.get(slug=dept_slug)
                user.save()
            if user_type == "ADMIN" and not user.is_staff:
                user.is_staff = True
                user.save(update_fields=["is_staff"])
            if user_type == "MERCHANT":
                now = timezone.now()
                user.mobile = user.mobile or "9876543210"
                user.email_verified_at = user.email_verified_at or now
                user.mobile_verified_at = user.mobile_verified_at or now
                user.save(update_fields=["mobile", "email_verified_at", "mobile_verified_at"])
            Policy.grant_role(user, role)
            self.stdout.write(f"{email} ({user_type})")
