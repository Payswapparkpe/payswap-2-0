from django.core.exceptions import PermissionDenied

from .models import Role, UserRole


class Policy:
    @staticmethod
    def permission_codenames(user) -> set[str]:
        if not user or not user.is_authenticated:
            return set()
        return set(UserRole.objects.filter(user=user).values_list("role__permissions__codename", flat=True))

    @staticmethod
    def grant_role(user, role_slug: str) -> None:
        role = Role.objects.get(slug=role_slug)
        UserRole.objects.get_or_create(user=user, role=role)

    @staticmethod
    def has_permission(user, action: str) -> bool:
        if not user or not user.is_authenticated or not user.is_active:
            return False
        return action in Policy.permission_codenames(user)

    @staticmethod
    def can(user, action: str, resource=None, **context) -> bool:
        if action.startswith("portal."):
            return Policy._portal(user, action)
        if not Policy.has_permission(user, action):
            return False
        if action == "merchant.view":
            return Policy._merchant_view(user, resource)
        if action == "order.approve":
            return Policy._order_approve(user, resource)
        if action in {"order.cancel", "order.amend"}:
            return Policy._order_owner_action(user, resource)
        return True

    @staticmethod
    def require(user, action: str, resource=None, **context):
        if not Policy.can(user, action, resource, **context):
            raise PermissionDenied("You do not have access to this action.")

    @staticmethod
    def _portal(user, action: str) -> bool:
        if not user or not user.is_authenticated or not user.is_active:
            return False
        mapping = {
            "portal.administration": user.user_type == user.UserType.ADMIN,
            "portal.employee": user.user_type == user.UserType.EMPLOYEE,
            "portal.merchant": user.user_type == user.UserType.MERCHANT,
        }
        return mapping.get(action, False)

    @staticmethod
    def _merchant_view(user, resource) -> bool:
        if resource is None:
            return True
        if user.user_type == user.UserType.ADMIN:
            return True
        if user.user_type == user.UserType.MERCHANT:
            return getattr(resource, "owner_id", None) == user.id
        if user.user_type == user.UserType.EMPLOYEE:
            role_slugs = set(UserRole.objects.filter(user=user).values_list("role__slug", flat=True))
            if "operations" in role_slugs:
                assigned_to = getattr(resource, "assigned_to_id", None)
                assigned_dept = getattr(resource, "assigned_department_id", None)
                if assigned_to is None and assigned_dept is None:
                    return True
                return assigned_to == user.id or assigned_dept == getattr(user, "department_id", None)
            return True
        return False

    @staticmethod
    def can_download_document(user, merchant) -> bool:
        if not Policy.can(user, "merchant.view", merchant):
            return False
        if user.user_type in {user.UserType.ADMIN, user.UserType.MERCHANT}:
            return True
        return any(
            Policy.has_permission(user, action)
            for action in ("kyc.approve", "merchant.review")
        )

    @staticmethod
    def _order_approve(user, resource) -> bool:
        if resource is None:
            return True
        return getattr(resource, "submitted_by_id", None) != user.id

    @staticmethod
    def _order_owner_action(user, resource) -> bool:
        """Merchant-side order actions (cancel/amend) are limited to the owner.

        Staff keep their rights through role permissions; the merchant owner may
        act on their own orders even though they hold no staff role.
        """
        if resource is None:
            return True
        if user.user_type in {user.UserType.ADMIN, user.UserType.EMPLOYEE}:
            return True
        merchant = getattr(resource, "merchant", None)
        return getattr(merchant, "owner_id", None) == user.id
