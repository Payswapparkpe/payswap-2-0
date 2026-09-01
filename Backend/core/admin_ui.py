from django.conf import settings


def environment_callback(request):
    if settings.IS_PRODUCTION:
        return ["Production", "danger"]
    if settings.APP_ENV == "staging":
        return ["Staging", "warning"]
    return ["Local", "info"]
