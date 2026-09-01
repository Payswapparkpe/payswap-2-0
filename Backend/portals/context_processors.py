from datetime import date

from django.conf import settings

from notifications.services import NotificationService
from portals.routing import LOGOUT_PATH

_PORTAL_ROUTES = {
    "administration": {
        "shell_layout": "layouts/administration.html",
        "search_url": "/administration/search/",
        "notifications_url": "/administration/notifications/",
        "home_url": "/administration/",
        "sessions_url": "/administration/sessions/",
        "security_url": "/administration/account/security/",
        "profile_url": "/administration/account/profile/",
        "label": "Administration",
    },
    "employee": {
        "shell_layout": "layouts/employee.html",
        "search_url": "/employee/search/",
        "notifications_url": "/employee/notifications/",
        "home_url": "/employee/",
        "sessions_url": "/employee/sessions/",
        "security_url": "/employee/account/security/",
        "profile_url": "/employee/profile/",
        "label": "Employee",
    },
    "merchant": {
        "shell_layout": "layouts/merchant.html",
        "search_url": "/merchant/search/",
        "notifications_url": "/merchant/notifications/",
        "home_url": "/merchant/",
        "sessions_url": "/merchant/sessions/",
        "security_url": "/merchant/account/security/",
        "profile_url": "/merchant/profile/",
        "label": "Merchant",
    },
}


def portal(request):
    path = request.path
    if path.startswith("/administration/"):
        name = "administration"
    elif path.startswith("/employee/"):
        name = "employee"
    elif path.startswith("/merchant/"):
        name = "merchant"
    else:
        name = ""
    routes = _PORTAL_ROUTES.get(name, {})
    return {
        "portal_name": name,
        "shell_layout": routes.get("shell_layout", "layouts/base.html"),
        "search_url": routes.get("search_url", "/"),
        "notifications_url": routes.get("notifications_url", "/"),
        "logout_url": LOGOUT_PATH,
        "home_url": routes.get("home_url", "/"),
        "sessions_url": routes.get("sessions_url", "/"),
        "security_url": routes.get("security_url", "/"),
        "profile_url": routes.get("profile_url", "/"),
        "support_url": "",
        "messages_url": "",
        "portal_label": routes.get("label", ""),
        "unread_notification_count": NotificationService.unread_count(getattr(request, "user", None)),
        "legal_entity_name": settings.LEGAL_ENTITY_NAME,
        "copyright_year": date.today().year,
        "grievance_officer_name": settings.GRIEVANCE_OFFICER_NAME,
        "grievance_email": settings.GRIEVANCE_EMAIL,
        "grievance_postal_address": settings.GRIEVANCE_POSTAL_ADDRESS,
    }
