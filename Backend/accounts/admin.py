from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import LoginEvent, User, UserSession


@admin.register(User)
class UserAdmin(ModelAdmin):
    ordering = ["email"]
    list_display = ["email", "user_type", "is_staff", "is_active", "mfa_enforced"]
    list_filter = ["user_type", "is_staff", "is_active", "mfa_enforced"]
    search_fields = ["email", "name", "mobile"]
    readonly_fields = ["last_activity_at", "date_joined"]


@admin.register(UserSession)
class UserSessionAdmin(ModelAdmin):
    list_display = ["user", "ip_address", "created_at", "revoked_at"]
    search_fields = ["user__email", "ip_address"]


@admin.register(LoginEvent)
class LoginEventAdmin(ModelAdmin):
    list_display = ["email", "result", "ip_address", "created_at"]
    search_fields = ["email", "ip_address"]
