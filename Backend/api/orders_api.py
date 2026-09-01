from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404

from catalog.models import VoucherProduct
from catalog.services import OrderPricingService
from orders.models import PaymentOrder
from orders.services import PaymentOrderService

from .mixins import JsonView, MerchantRequiredMixin, api_error, parse_json
from .serializers import catalog_payload, order_payload
from .onboarding import _merchant_context


class CatalogView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        return self.ok({"items": catalog_payload()})


class CatalogQuoteView(MerchantRequiredMixin, JsonView):
    def post(self, request):
        body = parse_json(request)
        product = get_object_or_404(VoucherProduct.objects.filter(is_active=True), pk=body.get("productId"))
        quantity = int(body.get("quantity") or 1)
        quote = OrderPricingService.quote(product, quantity)
        return self.ok(
            {
                "quantity": quote.quantity,
                "unitValue": float(quote.unit_value),
                "subtotal": float(quote.subtotal),
                "fees": float(quote.fees),
                "tax": float(quote.tax),
                "total": float(quote.total),
            }
        )


class OrderListCreateView(MerchantRequiredMixin, JsonView):
    def get(self, request):
        merchant, _application = _merchant_context(request.user)
        orders = PaymentOrder.objects.filter(merchant=merchant).select_related("product", "product__brand")
        return self.ok({"orders": [order_payload(order) for order in orders]})

    def post(self, request):
        body = parse_json(request)
        merchant, _application = _merchant_context(request.user)
        product = get_object_or_404(VoucherProduct.objects.filter(is_active=True), pk=body.get("productId"))
        quantity = int(body.get("quantity") or 1)
        submit = bool(body.get("submit", True))
        try:
            order = PaymentOrderService.create(
                merchant=merchant,
                actor=request.user,
                product=product,
                quantity=quantity,
                idempotency_key=body.get("idempotencyKey"),
            )
            if submit:
                PaymentOrderService.submit(order, actor=request.user, request=request)
                order.refresh_from_db()
        except ValidationError as exc:
            return api_error(" ".join(exc.messages))
        return self.ok({"order": order_payload(order)}, status=201)


class OrderDetailView(MerchantRequiredMixin, JsonView):
    def get(self, request, public_id):
        merchant, _application = _merchant_context(request.user)
        order = get_object_or_404(
            PaymentOrder.objects.select_related("product", "product__brand"),
            public_id=public_id,
            merchant=merchant,
        )
        return self.ok({"order": order_payload(order)})

    def post(self, request, public_id):
        body = parse_json(request)
        merchant, _application = _merchant_context(request.user)
        order = get_object_or_404(PaymentOrder, public_id=public_id, merchant=merchant)
        action = body.get("action")
        try:
            if action == "submit":
                PaymentOrderService.submit(order, actor=request.user, request=request)
            elif action == "cancel":
                PaymentOrderService.cancel(order, actor=request.user, reason=body.get("reason") or "", request=request)
            elif action == "edit":
                product = get_object_or_404(VoucherProduct.objects.filter(is_active=True), pk=body.get("productId"))
                quantity = int(body.get("quantity") or order.quantity)
                PaymentOrderService.edit_draft(
                    order=order,
                    actor=request.user,
                    product=product,
                    quantity=quantity,
                    request=request,
                )
            else:
                return api_error("Unsupported order action.")
        except ValidationError as exc:
            return api_error(" ".join(exc.messages))
        order.refresh_from_db()
        return self.ok({"order": order_payload(order)})
