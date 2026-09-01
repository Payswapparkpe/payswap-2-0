from django.shortcuts import render

from portals.routing import LOGIN_PATH, portal_home


def home_url_for(request) -> str:
    user = getattr(request, "user", None)
    if not user or not getattr(user, "is_authenticated", False):
        return LOGIN_PATH
    return portal_home(user)


def _render_error(request, *, status, template, title, message, extra=None):
    context = {
        "error_code": status,
        "error_title": title,
        "error_message": message,
        "home_url": home_url_for(request),
        **(extra or {}),
    }
    return render(request, template, context, status=status)


def bad_request(request, exception=None):
    return _render_error(
        request,
        status=400,
        template="errors/400.html",
        title="Bad request",
        message="The request could not be understood. Check the form and try again.",
    )


def permission_denied(request, exception=None):
    return _render_error(
        request,
        status=403,
        template="errors/403.html",
        title="Access denied",
        message="You do not have permission to open this page.",
    )


def csrf_failure(request, reason=""):
    return _render_error(
        request,
        status=403,
        template="errors/csrf.html",
        title="Session expired",
        message="This form is no longer valid. Refresh the page and submit it again.",
        extra={"reason": reason},
    )


def page_not_found(request, exception=None):
    return _render_error(
        request,
        status=404,
        template="errors/404.html",
        title="Page not found",
        message="That address is not a page on this site, or the record was removed.",
    )


def too_many_requests(request, exception=None):
    return _render_error(
        request,
        status=429,
        template="errors/429.html",
        title="Too many attempts",
        message="Wait a few minutes, then try again. Repeated failed sign-ins are limited to protect accounts.",
    )


def server_error(request):
    return _render_error(
        request,
        status=500,
        template="errors/500.html",
        title="Something went wrong",
        message="This request could not be completed. Try again, or return home if the problem continues.",
    )
