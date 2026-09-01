from django.db.models import Prefetch, Q

from access.policy import Policy
from agreements.models import Agreement
from merchants.models import Merchant, OnboardingApplication
from merchants.states import ApplicationStatus
from orders.models import PaymentOrder
from verification.models import Document


def search(user, query: str) -> list[dict]:
    query = (query or "").strip()
    if not query:
        return []
    results = []
    if Policy.can(user, "portal.merchant"):
        merchant = getattr(user, "merchant", None)
        if merchant:
            for order in PaymentOrder.objects.filter(merchant=merchant).filter(Q(public_id__icontains=query))[
                :10
            ]:
                results.append(
                    {
                        "label": f"Order {order.public_id}",
                        "url": f"/merchant/orders/{order.public_id}/",
                    }
                )
            for agreement in Agreement.objects.filter(merchant=merchant, public_id__icontains=query)[:5]:
                results.append({"label": f"Agreement {agreement.public_id}", "url": "/merchant/agreements/"})
        return results
    if not (Policy.can(user, "portal.administration") or Policy.can(user, "portal.employee")):
        return []
    prefix = "/administration" if Policy.can(user, "portal.administration") else "/employee"
    merchants = Merchant.objects.filter(
        Q(public_id__icontains=query) | Q(business_name__icontains=query) | Q(owner__email__icontains=query)
    )
    if prefix == "/employee":
        # The employee route reviews applications, not merchants — resolve the
        # merchant's latest reviewable application for a working link.
        merchants = merchants.prefetch_related(
            Prefetch(
                "applications",
                queryset=OnboardingApplication.objects.exclude(status=ApplicationStatus.DRAFT).order_by(
                    "-created_at"
                ),
            )
        )
    for merchant in merchants[:10]:
        if Policy.can(user, "merchant.view", merchant):
            if prefix == "/administration":
                url = f"/administration/merchants/{merchant.public_id}/"
            else:
                apps = list(merchant.applications.all())
                application = apps[0] if apps else None
                url = f"/employee/queue/{application.public_id}/" if application else "/employee/queue/"
            results.append({"label": f"Merchant {merchant.public_id}", "url": url})
    for order in PaymentOrder.objects.filter(public_id__icontains=query)[:10]:
        if Policy.can(user, "merchant.view", order.merchant):
            results.append(
                {
                    "label": f"Order {order.public_id}",
                    "url": f"{prefix}/orders/{order.public_id}/"
                    if prefix == "/employee"
                    else f"/administration/orders/?q={order.public_id}",
                }
            )
    for document in Document.objects.filter(public_id__icontains=query)[:5]:
        if Policy.can(user, "merchant.view", document.merchant):
            results.append({"label": f"Document {document.public_id}", "url": "/administration/merchants/"})
    return results
