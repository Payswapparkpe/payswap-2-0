from django.db import models


class ServiceType(models.Model):
    code = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=False)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self):
        return self.name


class Brand(models.Model):
    service_type = models.ForeignKey(ServiceType, on_delete=models.CASCADE, related_name="brands")
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=80)
    is_active = models.BooleanField(default=True)

    class Meta:
        indexes = [models.Index(fields=["is_active"])]

    def __str__(self):
        return self.name


class VoucherProduct(models.Model):
    brand = models.ForeignKey(Brand, on_delete=models.CASCADE, related_name="products")
    name = models.CharField(max_length=120)
    denomination = models.DecimalField(max_digits=12, decimal_places=2)
    fee_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=4, default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("brand", "denomination")
        indexes = [
            models.Index(fields=["is_active", "brand"]),
        ]

    def __str__(self):
        return self.name
