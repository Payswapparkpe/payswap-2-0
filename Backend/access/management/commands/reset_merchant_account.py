from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from merchants.services import MerchantOnboardingService


class Command(BaseCommand):
    help = "Reset a merchant onboarding file (KYC/KYB/agreements) and optionally change login email."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True, help="Current account email.")
        parser.add_argument(
            "--set-email",
            dest="set_email",
            default="",
            help="Optional new login email (e.g. move yahoo.com account to payswap.in).",
        )

    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        set_email = (options.get("set_email") or "").strip().lower()
        User = get_user_model()
        user = User.objects.filter(email=email).first()
        if user is None:
            raise CommandError(f"No user found for {email}")

        application = MerchantOnboardingService.reset_onboarding(user, new_email=set_email)
        user.refresh_from_db()
        merchant = getattr(user, "merchant", None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reset complete for {user.email} · User ID {user.public_id}"
                + (f" · Merchant {merchant.public_id}" if merchant else "")
                + f" · Application {application.public_id} (draft)"
            )
        )
