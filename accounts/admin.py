from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "get_full_name", "email", "role", "receives_stock_alerts", "is_active")
    list_filter = ("role", "receives_stock_alerts", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("What this person can do", {"fields": ("role", "phone", "receives_stock_alerts")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("What this person can do", {"fields": ("role", "phone", "email", "receives_stock_alerts")}),
    )
