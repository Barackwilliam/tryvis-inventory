from django.contrib import admin, messages

from purchasing.models import Purchase, PurchaseLine, PurchaseStatus


class PurchaseLineInline(admin.TabularInline):
    model = PurchaseLine
    extra = 3
    autocomplete_fields = ("item",)
    readonly_fields = ("allocated_charges", "landed_unit_cost")


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = (
        "reference", "supplier", "purchase_date", "currency",
        "status", "supplier_invoice_no",
    )
    list_filter = ("status", "currency", "supplier")
    search_fields = ("reference", "supplier__name", "supplier_invoice_no")
    readonly_fields = ("reference", "received_at")
    autocomplete_fields = ("supplier",)
    inlines = [PurchaseLineInline]
    actions = ["receive_into_stock"]
    fieldsets = (
        ("The paperwork", {"fields": ("reference", "supplier", "supplier_invoice_no", "purchase_date", "status", "received_at")}),
        ("What you paid in", {"fields": ("currency", "exchange_rate")}),
        ("Shipping, customs and clearing", {
            "fields": ("freight_cost", "customs_duty", "clearing_charges", "other_charges", "allocation_method"),
            "description": "These are shared across the items below when you add the stock to the store, "
                           "so you can see what each piece really cost.",
        }),
        ("Notes", {"fields": ("notes",)}),
    )

    @admin.action(description="Add these to the store")
    def receive_into_stock(self, request, queryset):
        done, failed = 0, 0
        for purchase in queryset:
            try:
                purchase.receive(user=request.user)
                done += 1
            except Exception as exc:
                failed += 1
                self.message_user(request, f"{purchase.reference}: {exc}", messages.ERROR)
        if done:
            self.message_user(request, f"{done} lot(s) added to the store.", messages.SUCCESS)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_readonly_fields(self, request, obj=None):
        fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == PurchaseStatus.RECEIVED:
            fields += ["supplier", "currency", "exchange_rate", "freight_cost",
                       "customs_duty", "clearing_charges", "other_charges",
                       "allocation_method", "purchase_date"]
        return fields
