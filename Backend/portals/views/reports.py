from django.shortcuts import render
from django.views import View

from access.models import Role
from access.policy import Policy
from orders.models import PaymentOrder
from portals.mixins import AdministrationRequiredMixin, EmployeeRequiredMixin
from portals.pagination import paginate


class AdminRoleView(AdministrationRequiredMixin, View):
    def get(self, request):
        Policy.require(request.user, "role.manage")
        return render(
            request,
            "portals/administration/roles.html",
            {"roles": Role.objects.prefetch_related("permissions").all()},
        )


class EmployeeOrderListView(EmployeeRequiredMixin, View):
    def get(self, request):
        if any(
            Policy.has_permission(request.user, permission)
            for permission in ("order.review", "order.approve", "order.reject", "order.request_changes")
        ):
            orders = PaymentOrder.objects.select_related("merchant", "product")
        else:
            orders = PaymentOrder.objects.none()
        page, querystring = paginate(request, orders)
        return render(
            request,
            "portals/employee/orders.html",
            {"orders": page.object_list, "page": page, "querystring": querystring},
        )
