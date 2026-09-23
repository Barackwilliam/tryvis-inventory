from django.contrib import admin

from inventory.models import StockAlertLog, StockMovement


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    """Read only on purpose. The ledger is corrected with counter-movements."""

    list_display = (
        "movement_date", "item", "movement_type", "quantity",
        "balance_after", "source_reference", "created_by",
    )
    list_filter = ("movement_type", "movement_date")
    search_fields = ("item__code", "item__name", "source_reference", "notes")
    date_hierarchy = "movement_date"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(StockAlertLog)
class StockAlertLogAdmin(admin.ModelAdmin):
    list_display = ("item", "quantity_at_alert", "minimum_at_alert", "sent_at", "cleared_at")
    list_filter = ("sent_at", "cleared_at")
    search_fields = ("item__code", "item__name")
