from datetime import timedelta

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from access.models import Role, UserRole
from access.policy import Policy
from accounts.models import LoginEvent, User
from agreements.services import AgreementService
from audit.models import AuditEvent
from audit.services import AuditService
from merchants.models import Merchant, OnboardingApplication
from merchants.services import MerchantOnboardingService
from merchants.states import ApplicationStatus
from orders.models import OrderStatus, PaymentOrder
from portals.charts import attach_pct
from portals.mixins import AdministrationRequiredMixin
from portals.pagination import paginate
from verification.models import Document, VerificationRecord
from verification.services import DocumentReviewService


def _age_bucket(dt):
    if not dt:
        return "> 24 hours"
    delta = timezone.now() - dt
    hours = delta.total_seconds() / 3600
    if hours < 2:
        return "< 2 hours"
    if hours < 8:
        return "2–8 hours"
    if hours < 24:
        return "8–24 hours"
    return "> 24 hours"


class AdminDashboardView(AdministrationRequiredMixin, View):
    def get(self, request):
        today = timezone.now().date()
        kpis = [
            {
                "label": "Active Merchants",
                "value": Merchant.objects.filter(status=Merchant.Status.ACTIVE).count(),
                "url": "/administration/merchants/?status=ACTIVE",
            },
            {
                "label": "Pending Merchant Reviews",
                "value": OnboardingApplication.objects.filter(
                    status__in=[ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]
                ).count(),
                "url": "/administration/onboarding/?status=SUBMITTED",
            },
            {
                "label": "Orders Today",
                "value": PaymentOrder.objects.filter(created_at__date=today).count(),
                "url": "/administration/orders/?date=today",
            },
            {
                "label": "Orders Awaiting Approval",
                "value": PaymentOrder.objects.filter(
                    status__in=[OrderStatus.SUBMITTED, OrderStatus.UNDER_REVIEW]
                ).count(),
                "url": "/administration/orders/?status=UNDER_REVIEW",
            },
            {
                "label": "Approved Orders Today",
                "value": PaymentOrder.objects.filter(
                    status=OrderStatus.APPROVED,
                    updated_at__date=today,
                ).count(),
                "url": "/administration/orders/?status=APPROVED",
            },
            {
                "label": "Failed Operations",
                "value": AuditEvent.objects.filter(result="failure", created_at__date=today).count(),
                "url": "/administration/audit/?result=failure",
            },
            {
                "label": "Security Alerts",
                "value": LoginEvent.objects.filter(
                    result=LoginEvent.Result.FAILURE, created_at__date=today
                ).count(),
                "url": "/administration/security/",
            },
        ]
        attention = []
        for app in OnboardingApplication.objects.filter(
            status__in=[ApplicationStatus.SUBMITTED, ApplicationStatus.UNDER_REVIEW]
        ).select_related("merchant")[:20]:
            attention.append(
                {
                    "priority": "High",
                    "label": "Merchant review",
                    "ref": app.public_id,
                    "age": _age_bucket(app.submitted_at or app.created_at),
                    "owner": app.reviewed_by or "Unassigned",
                    "status": app.get_status_display(),
                    "url": f"/administration/merchants/{app.merchant.public_id}/",
                }
            )
        return render(
            request,
            "portals/administration/dashboard.html",
            {"kpis": attach_pct(kpis, key="value"), "attention": attention},
        )


class AdminVerificationDashboardView(AdministrationRequiredMixin, View):
    """Cross-merchant verification oversight with lifecycle actions."""

    def get(self, request):
        Policy.require(request.user, "merchant.view")
        records = VerificationRecord.objects.select_related("merchant", "requested_by").all()
        vtype = request.GET.get("type")
        status = request.GET.get("status")
        q = request.GET.get("q", "").strip()
        if vtype:
            records = records.filter(verification_type=vtype)
        if status:
            records = records.filter(status=status)
        if q:
            records = records.filter(
                Q(merchant__business_name__icontains=q)
                | Q(merchant__public_id__icontains=q)
                | Q(document_masked__icontains=q)
                | Q(reference_id__icontains=q)
            )
        cards = [
            {
                "label": "Verified (active)",
                "value": VerificationRecord.objects.filter(
                    status=VerificationRecord.Status.VERIFIED,
                    expires_at__gt=timezone.now(),
                ).count(),
                "url": "/administration/verification/?status=VERIFIED",
            },
            {
                "label": "Pending / processing",
                "value": VerificationRecord.objects.filter(
                    status__in=[
                        VerificationRecord.Status.PENDING,
                        VerificationRecord.Status.PROCESSING,
                    ]
                ).count(),
                "url": "/administration/verification/?status=PENDING",
            },
            {
                "label": "Failed",
                "value": VerificationRecord.objects.filter(status=VerificationRecord.Status.FAILED).count(),
                "url": "/administration/verification/?status=FAILED",
            },
            {
                "label": "Expiring in 7 days",
                "value": VerificationRecord.objects.filter(
                    status=VerificationRecord.Status.VERIFIED,
                    expires_at__range=(
                        timezone.now(),
                        timezone.now() + timedelta(days=7),
                    ),
                ).count(),
                "url": "/administration/verification/?status=VERIFIED",
            },
            {
                "label": "Reused (30-day cache)",
                "value": VerificationRecord.objects.filter(reused_from__isnull=False).count(),
                "url": "/administration/verification/",
            },
        ]
        page, querystring = paginate(request, records)
        return render(
            request,
            "portals/administration/verification.html",
            {
                "records": page.object_list,
                "cards": attach_pct(cards, key="value"),
                "page": page,
                "querystring": querystring,
                "filters": request.GET,
                "type_choices": VerificationRecord.Type.choices,
                "status_choices": VerificationRecord.Status.choices,
            },
        )

    def post(self, request):
        Policy.require(request.user, "merchant.manage")
        record = get_object_or_404(VerificationRecord, public_id=request.POST.get("record", ""))
        action = request.POST.get("action", "")
        if action == "expire":
            record.status = VerificationRecord.Status.EXPIRED
            record.expires_at = timezone.now()
            record.save(update_fields=["status", "expires_at"])
            AuditService.record(
                actor=request.user,
                action="verification.expire",
                resource_type="verification",
                resource_id=record.public_id,
                request=request,
            )
            messages.success(
                request,
                f"{record.get_verification_type_display()} for "
                f"{record.merchant.business_name} was expired; the next attempt re-verifies with Cashfree.",
            )
        else:
            messages.error(request, "Unknown action.")
        return redirect(request.get_full_path())


class MerchantListView(AdministrationRequiredMixin, View):
    def get(self, request):
        merchants = Merchant.objects.select_related("owner", "assigned_to").all()
        status = request.GET.get("status")
        entity = request.GET.get("entity_type")
        if status:
            merchants = merchants.filter(status=status)
        if entity:
            merchants = merchants.filter(entity_type=entity)
        q = request.GET.get("q")
        if q:
            merchants = merchants.filter(
                Q(public_id__icontains=q) | Q(business_name__icontains=q) | Q(owner__email__icontains=q)
            )
        page, querystring = paginate(request, merchants)
        return render(
            request,
            "portals/administration/merchants.html",
            {"merchants": page.object_list, "filters": request.GET, "page": page, "querystring": querystring},
        )


@method_decorator(ratelimit(key="user_or_ip", rate="20/m", method="POST", block=True), name="dispatch")
class MerchantDetailView(AdministrationRequiredMixin, View):
    def get(self, request, public_id):
        merchant = get_object_or_404(Merchant.objects.select_related("owner"), public_id=public_id)
        Policy.require(request.user, "merchant.view", merchant)
        application = merchant.applications.order_by("-created_at").first()
        tab = request.GET.get("tab", "overview")
        return render(
            request,
            "portals/administration/merchant_detail.html",
            {
                "merchant": merchant,
                "application": application,
                "tab": tab,
                "documents": merchant.documents.select_related("reviewed_by", "uploaded_by").all(),
                "orders": merchant.orders.all()[:20],
                "agreements": merchant.agreements.all(),
                "audit_events": AuditEvent.objects.filter(resource_id=merchant.public_id)[:30],
                "employees": User.objects.filter(user_type=User.UserType.EMPLOYEE),
            },
        )

    def post(self, request, public_id):
        merchant = get_object_or_404(Merchant, public_id=public_id)
        action = request.POST.get("action")
        application = merchant.applications.order_by("-created_at").first()
        try:
            if action == "assign":
                Policy.require(request.user, "merchant.assign", merchant)
                previous = merchant.assigned_to_id
                merchant.assigned_to_id = request.POST.get("assigned_to") or None
                merchant.save(update_fields=["assigned_to"])
                AuditService.record(
                    actor=request.user,
                    action="merchant.assign",
                    resource_type="merchant",
                    resource_id=merchant.public_id,
                    before={"assigned_to": previous},
                    after={"assigned_to": merchant.assigned_to_id},
                    request=request,
                )
                messages.success(request, "Assignment updated.")
            elif action == "clarification" and application:
                if application.status == ApplicationStatus.SUBMITTED:
                    MerchantOnboardingService.start_review(application, actor=request.user, request=request)
                MerchantOnboardingService.request_clarification(
                    application,
                    actor=request.user,
                    step_key=request.POST.get("step_key", "bank"),
                    message=request.POST.get("message", ""),
                    request=request,
                )
            elif action == "approve" and application:
                from accounts.services import StepUpService

                StepUpService.require(request.user, request.session)
                if application.status == ApplicationStatus.SUBMITTED:
                    MerchantOnboardingService.start_review(application, actor=request.user, request=request)
                MerchantOnboardingService.approve(application, actor=request.user, request=request)
                messages.success(request, "Merchant application approved.")
            elif action == "reject" and application:
                if application.status == ApplicationStatus.SUBMITTED:
                    MerchantOnboardingService.start_review(application, actor=request.user, request=request)
                MerchantOnboardingService.reject(
                    application,
                    actor=request.user,
                    reason=request.POST.get("reason", "Other"),
                    notes=request.POST.get("notes", ""),
                    request=request,
                )
            elif action == "suspend":
                Policy.require(request.user, "merchant.suspend", merchant)
                before = {"status": merchant.status, "commercial_status": merchant.commercial_status}
                merchant.status = Merchant.Status.SUSPENDED
                merchant.commercial_status = Merchant.CommercialStatus.SUSPENDED
                merchant.save(update_fields=["status", "commercial_status"])
                AuditService.record(
                    actor=request.user,
                    action="merchant.suspend",
                    resource_type="merchant",
                    resource_id=merchant.public_id,
                    before=before,
                    after={"status": merchant.status, "commercial_status": merchant.commercial_status},
                    request=request,
                )
                messages.success(request, "Merchant suspended.")
            elif action == "reactivate":
                Policy.require(request.user, "merchant.suspend", merchant)
                before = {"status": merchant.status, "commercial_status": merchant.commercial_status}
                merchant.status = Merchant.Status.ACTIVE
                merchant.commercial_status = Merchant.CommercialStatus.ACTIVE
                merchant.save(update_fields=["status", "commercial_status"])
                AuditService.record(
                    actor=request.user,
                    action="merchant.reactivate",
                    resource_type="merchant",
                    resource_id=merchant.public_id,
                    before=before,
                    after={"status": merchant.status, "commercial_status": merchant.commercial_status},
                    request=request,
                )
                messages.success(request, "Merchant reactivated.")
            elif action == "generate_agreement":
                AgreementService.generate(merchant=merchant, actor=request.user, request=request)
            elif action == "countersign":
                agreement = merchant.agreements.order_by("-created_at").first()
                if agreement:
                    AgreementService.countersign(agreement=agreement, actor=request.user, request=request)
        except ValidationError as exc:
            messages.error(request, " ".join(exc.messages))
        return redirect(f"/administration/merchants/{public_id}/")


class OnboardingQueueView(AdministrationRequiredMixin, View):
    def get(self, request):
        apps = OnboardingApplication.objects.select_related("merchant").exclude(
            status=ApplicationStatus.DRAFT
        )
        status = request.GET.get("status")
        if status:
            apps = apps.filter(status=status)
        page, querystring = paginate(request, apps)
        return render(
            request,
            "portals/administration/onboarding.html",
            {"applications": page.object_list, "page": page, "querystring": querystring},
        )


class OrderListView(AdministrationRequiredMixin, View):
    def get(self, request):
        orders = PaymentOrder.objects.select_related("merchant", "product")
        status = request.GET.get("status")
        if status:
            orders = orders.filter(status=status)
        if request.GET.get("date") == "today":
            orders = orders.filter(created_at__date=timezone.now().date())
        date_from = request.GET.get("date_from")
        date_to = request.GET.get("date_to")
        if date_from:
            orders = orders.filter(created_at__date__gte=date_from)
        if date_to:
            orders = orders.filter(created_at__date__lte=date_to)
        page, querystring = paginate(request, orders)
        return render(
            request,
            "portals/administration/orders.html",
            {
                "orders": page.object_list,
                "date_from": date_from or "",
                "date_to": date_to or "",
                "page": page,
                "querystring": querystring,
            },
        )


class EmployeeListView(AdministrationRequiredMixin, View):
    def get(self, request):
        Policy.require(request.user, "role.manage")
        employees = (
            User.objects.filter(user_type=User.UserType.EMPLOYEE)
            .select_related("department")
            .prefetch_related("user_roles__role")
        )
        page, querystring = paginate(request, employees)
        return render(
            request,
            "portals/administration/employees.html",
            {
                "employees": page.object_list,
                "roles": Role.objects.exclude(slug="merchant"),
                "page": page,
                "querystring": querystring,
            },
        )


class EmployeeRoleView(AdministrationRequiredMixin, View):
    """Grant or revoke a single role on an employee account."""

    def post(self, request, user_id):
        Policy.require(request.user, "role.manage")
        employee = get_object_or_404(User, pk=user_id, user_type=User.UserType.EMPLOYEE)
        role = get_object_or_404(Role.objects.exclude(slug="merchant"), slug=request.POST.get("role"))
        action = request.POST.get("action")
        membership = UserRole.objects.filter(user=employee, role=role)
        if action == "grant":
            if employee.pk == request.user.pk and role.slug != "platform_admin":
                messages.error(request, "You cannot change your own roles.")
                return redirect("/administration/employees/")
            _, created = UserRole.objects.get_or_create(user=employee, role=role)
            if not created:
                messages.info(request, f"{employee.email} already has the {role.name} role.")
                return redirect("/administration/employees/")
            result = "granted"
        elif action == "revoke":
            if employee.pk == request.user.pk:
                messages.error(request, "You cannot change your own roles.")
                return redirect("/administration/employees/")
            if not membership.exists():
                messages.info(request, f"{employee.email} does not hold the {role.name} role.")
                return redirect("/administration/employees/")
            membership.delete()
            result = "revoked"
        else:
            messages.error(request, "Unknown role action.")
            return redirect("/administration/employees/")
        AuditService.record(
            actor=request.user,
            action=f"role.{result}",
            resource_type="user",
            resource_id=str(employee.pk),
            after={"email": employee.email, "role": role.slug},
            request=request,
        )
        messages.success(request, f"Role {role.name} {result} for {employee.email}.")
        return redirect("/administration/employees/")


class AuditListView(AdministrationRequiredMixin, View):
    def get(self, request):
        Policy.require(request.user, "audit.view")
        events = AuditEvent.objects.select_related("actor")
        if request.GET.get("action"):
            events = events.filter(action__icontains=request.GET["action"])
        if request.GET.get("result"):
            events = events.filter(result=request.GET["result"])
        if request.GET.get("from"):
            events = events.filter(created_at__date__gte=request.GET["from"])
        page, querystring = paginate(request, events, per_page=50)
        return render(
            request,
            "portals/administration/audit.html",
            {"events": page.object_list, "page": page, "querystring": querystring},
        )


class SecurityCenterView(AdministrationRequiredMixin, View):
    def get(self, request):
        Policy.require(request.user, "security.manage")
        since = timezone.now() - timedelta(days=7)
        page, querystring = paginate(
            request,
            LoginEvent.objects.filter(result=LoginEvent.Result.FAILURE, created_at__gte=since),
        )
        users_page, users_querystring = paginate(
            request,
            User.objects.exclude(user_type=User.UserType.ADMIN).order_by("email"),
            per_page=50,
            page_param="upage",
        )
        return render(
            request,
            "portals/administration/security.html",
            {
                "failed_logins": page.object_list,
                "page": page,
                "querystring": querystring,
                "privileged": AuditEvent.objects.filter(
                    action__in=[
                        "merchant.approve",
                        "role.manage",
                        "security.force_logout",
                        "security.reset_mfa",
                        "security.suspend",
                    ]
                )[:50],
                "managed_users": users_page.object_list,
                "users_page": users_page,
                "users_querystring": users_querystring,
            },
        )


class DocumentReviewView(AdministrationRequiredMixin, View):
    def post(self, request, public_id):
        document = get_object_or_404(Document, public_id=public_id)
        action = request.POST.get("action")
        if action == "approve":
            DocumentReviewService.approve(document=document, actor=request.user, request=request)
        elif action == "reject":
            DocumentReviewService.reject(
                document=document, actor=request.user, reason=request.POST.get("reason", ""), request=request
            )
        return redirect(f"/administration/merchants/{document.merchant.public_id}/?tab=documents")
