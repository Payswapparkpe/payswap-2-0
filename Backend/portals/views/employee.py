from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from access.models import UserRole
from access.policy import Policy
from merchants.models import OnboardingApplication
from merchants.review import (
    CLARIFICATION_SECTIONS,
    documents_for_review,
    staff_review_context,
)
from merchants.services import MerchantOnboardingService
from merchants.states import ApplicationStatus
from orders.models import OrderStatus, PaymentOrder
from orders.services import PaymentOrderService
from portals.mixins import ActionRequiredMixin, EmployeeRequiredMixin
from portals.pagination import paginate
from verification.models import VerificationRecord


class EmployeeDashboardView(EmployeeRequiredMixin, View):
    def get(self, request):
        roles = set(UserRole.objects.filter(user=request.user).values_list("role__slug", flat=True))
        queue = {
            "kyc_reviews": OnboardingApplication.objects.filter(
                status__in=[ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]
            ).count()
            if "kyc" in roles or "compliance" in roles
            else 0,
            "kyb_reviews": OnboardingApplication.objects.filter(status=ApplicationStatus.UNDER_REVIEW).count()
            if "kyc" in roles
            else 0,
            "clarifications": OnboardingApplication.objects.filter(
                status=ApplicationStatus.CLARIFICATION_REQUIRED
            ).count()
            if "kyc" in roles or "support" in roles
            else 0,
            "orders": PaymentOrder.objects.filter(
                status__in=[OrderStatus.SUBMITTED, OrderStatus.UNDER_REVIEW]
            ).count()
            if "operations" in roles
            else 0,
        }
        return render(
            request,
            "portals/employee/dashboard.html",
            {"queue": queue, "roles": roles},
        )


class EmployeeQueueView(EmployeeRequiredMixin, View):
    def get(self, request):
        roles = set(UserRole.objects.filter(user=request.user).values_list("role__slug", flat=True))
        applications = OnboardingApplication.objects.none()
        orders = PaymentOrder.objects.none()
        if roles & {"kyc", "compliance", "support"}:
            applications = OnboardingApplication.objects.exclude(
                status=ApplicationStatus.DRAFT
            ).select_related("merchant", "merchant__owner")
        if "operations" in roles:
            orders = PaymentOrder.objects.exclude(
                status__in=[OrderStatus.DRAFT, OrderStatus.APPROVED, OrderStatus.CANCELLED, OrderStatus.REJECTED]
            ).select_related("merchant", "product")
        app_page, querystring = paginate(request, applications, per_page=50)
        order_page, _ = paginate(request, orders, per_page=50)
        return render(
            request,
            "portals/employee/queue.html",
            {
                "applications": app_page.object_list,
                "orders": order_page.object_list,
                "page": app_page if app_page.paginator.count else order_page,
                "querystring": querystring,
                "roles": roles,
            },
        )


class EmployeeApplicationView(EmployeeRequiredMixin, ActionRequiredMixin, View):
    required_action = "merchant.review"

    def get_policy_resource(self):
        application = get_object_or_404(OnboardingApplication, public_id=self.kwargs["public_id"])
        return application.merchant

    def get(self, request, public_id):
        application = get_object_or_404(OnboardingApplication, public_id=public_id)
        Policy.require(request.user, "merchant.review", application.merchant)
        documents = list(application.merchant.documents.all())
        verifications = list(VerificationRecord.objects.filter(merchant=application.merchant).order_by("-requested_at")[:50])
        review_context = staff_review_context(
            request=request,
            merchant=application.merchant,
            application=application,
            verifications=verifications,
        )
        return render(
            request,
            "portals/employee/application.html",
            {
                "application": application,
                "merchant": application.merchant,
                "clarification_sections": CLARIFICATION_SECTIONS,
                "documents": documents,
                "document_cards": documents_for_review(documents),
                "verifications": verifications,
                **review_context,
            },
        )

    def post(self, request, public_id):
        application = get_object_or_404(OnboardingApplication, public_id=public_id)
        action = request.POST.get("action")
        try:
            if application.status == ApplicationStatus.SUBMITTED:
                MerchantOnboardingService.start_review(application, actor=request.user, request=request)
            if action == "approve":
                MerchantOnboardingService.approve(application, actor=request.user, request=request)
                messages.success(request, "Application approved.")
            elif action == "reject":
                MerchantOnboardingService.reject(
                    application,
                    actor=request.user,
                    reason=request.POST.get("reason", "Other"),
                    request=request,
                )
            elif action == "clarification":
                MerchantOnboardingService.request_clarification(
                    application,
                    actor=request.user,
                    step_key=request.POST.get("step_key", "bank"),
                    message=request.POST.get("message", ""),
                    request=request,
                )
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect(f"/employee/queue/{public_id}/")


@method_decorator(ratelimit(key="user_or_ip", rate="10/m", method="POST", block=True), name="dispatch")
class EmployeeOrderView(EmployeeRequiredMixin, View):
    _ANY_ORDER_PERMISSION = (
        "order.review",
        "order.approve",
        "order.reject",
        "order.request_changes",
        "order.cancel",
        "order.amend",
    )

    def _check_access(self, request):
        if not any(
            Policy.has_permission(request.user, permission) for permission in self._ANY_ORDER_PERMISSION
        ):
            raise PermissionDenied("You do not have access to orders.")

    def get(self, request, public_id):
        self._check_access(request)
        order = get_object_or_404(
            PaymentOrder.objects.select_related("merchant", "product").prefetch_related(
                "events", "decisions__actor", "revisions"
            ),
            public_id=public_id,
        )
        can = lambda permission: Policy.has_permission(request.user, permission)  # noqa: E731
        return render(
            request,
            "portals/employee/order.html",
            {
                "order": order,
                "can_review": can("order.review") and order.status == OrderStatus.SUBMITTED,
                "can_approve": can("order.approve")
                and order.status == OrderStatus.UNDER_REVIEW
                and order.submitted_by_id != request.user.id,
                "can_reject": can("order.reject")
                and order.status in {OrderStatus.SUBMITTED, OrderStatus.UNDER_REVIEW},
                "can_request_changes": can("order.request_changes")
                and order.status == OrderStatus.UNDER_REVIEW,
                "can_amend": can("order.amend") and order.status == OrderStatus.APPROVED,
            },
        )

    def post(self, request, public_id):
        self._check_access(request)
        order = get_object_or_404(PaymentOrder, public_id=public_id)
        action = request.POST.get("action")
        reason = request.POST.get("reason", "")
        try:
            if action == "review":
                PaymentOrderService.transition(
                    order, OrderStatus.UNDER_REVIEW, actor=request.user, request=request
                )
                messages.success(request, "Order is now under review.")
            elif action == "approve":
                PaymentOrderService.transition(
                    order, OrderStatus.APPROVED, actor=request.user, request=request
                )
                messages.success(request, "Order approved.")
            elif action == "reject":
                PaymentOrderService.transition(
                    order, OrderStatus.REJECTED, actor=request.user, reason=reason, request=request
                )
                messages.success(request, "Order rejected.")
            elif action == "request_changes":
                PaymentOrderService.transition(
                    order,
                    OrderStatus.CHANGES_REQUESTED,
                    actor=request.user,
                    reason=reason,
                    request=request,
                )
                messages.success(request, "Changes requested from the merchant.")
            elif action == "amend":
                product = order.product
                try:
                    quantity = int(request.POST.get("quantity") or order.quantity)
                except (TypeError, ValueError):
                    quantity = order.quantity
                PaymentOrderService.amend(
                    order=order, actor=request.user, product=product, quantity=quantity, request=request
                )
                messages.success(request, "Order amended. It is back under review.")
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect(f"/employee/orders/{public_id}/")
