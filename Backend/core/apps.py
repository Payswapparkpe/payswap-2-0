from django.contrib.admin.apps import AdminConfig


class PayswapAdminConfig(AdminConfig):
    default_site = "core.admin.PayswapAdminSite"

    def ready(self):
        from django.contrib import admin
        from django.contrib.admin import sites

        from core.admin import PayswapAdminSite

        site = PayswapAdminSite(name="admin")
        admin.site = site
        sites.site = site
        super().ready()
