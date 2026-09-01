from decimal import Decimal

from django.core.management.base import BaseCommand

from access.seeds import seed_access_control
from catalog.models import Brand, ServiceType, VoucherProduct


class Command(BaseCommand):
    help = "Seed roles, departments, and the branded voucher catalog."

    # Major voucher brands with their common denominations (INR).
    BRANDS = {
        "amazon": ("Amazon", ["500.00", "1000.00", "2000.00", "5000.00"]),
        "flipkart": ("Flipkart", ["500.00", "1000.00", "2500.00"]),
        "google-play": ("Google Play", ["100.00", "300.00", "500.00"]),
        "swiggy": ("Swiggy", ["250.00", "500.00", "1000.00"]),
        "zomato": ("Zomato", ["250.00", "500.00", "1000.00"]),
        "bigbasket": ("BigBasket", ["500.00", "1000.00"]),
        "myntra": ("Myntra", ["500.00", "1000.00", "2000.00"]),
        "uber": ("Uber", ["200.00", "500.00", "1000.00"]),
        "bookmyshow": ("BookMyShow", ["250.00", "500.00"]),
        "makemytrip": ("MakeMyTrip", ["1000.00", "5000.00"]),
        "dominos": ("Domino's Pizza", ["300.00", "500.00"]),
        "pvr-inox": ("PVR INOX", ["250.00", "500.00"]),
    }

    def handle(self, *args, **options):
        seed_access_control()
        voucher, _ = ServiceType.objects.get_or_create(
            code="BRANDED_VOUCHER",
            defaults={"name": "Branded Voucher", "is_active": True},
        )
        voucher.is_active = True
        voucher.save(update_fields=["is_active"])
        ServiceType.objects.filter(code__in=["AEPS", "DMT", "BBPS", "FASTAG"]).delete()
        created = 0
        for slug, (name, denominations) in self.BRANDS.items():
            brand, _ = Brand.objects.get_or_create(
                slug=slug, defaults={"name": name, "service_type": voucher}
            )
            if brand.service_type_id != voucher.id:
                brand.service_type = voucher
                brand.save(update_fields=["service_type"])
            for amount in denominations:
                _, was_created = VoucherProduct.objects.get_or_create(
                    brand=brand,
                    denomination=Decimal(amount),
                    defaults={
                        "name": f"{name} ₹{amount.split('.')[0]}",
                        "fee_rate": Decimal("0.02"),
                        "tax_rate": Decimal("0.18"),
                    },
                )
                created += was_created
        self.stdout.write(
            f"Seeded access control and voucher catalog ({len(self.BRANDS)} brands, {created} new products)."
        )
