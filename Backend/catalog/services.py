from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from .models import VoucherProduct


def money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class PriceQuote:
    quantity: int
    unit_value: Decimal
    subtotal: Decimal
    fees: Decimal
    tax: Decimal
    total: Decimal


class OrderPricingService:
    @staticmethod
    def quote(product: VoucherProduct, quantity: int) -> PriceQuote:
        if quantity < 1:
            raise ValueError("Quantity must be at least 1.")
        unit = money(product.denomination)
        subtotal = money(unit * quantity)
        fees = money(subtotal * product.fee_rate)
        tax = money(fees * product.tax_rate)
        return PriceQuote(
            quantity=quantity,
            unit_value=unit,
            subtotal=subtotal,
            fees=fees,
            tax=tax,
            total=money(subtotal + fees + tax),
        )
