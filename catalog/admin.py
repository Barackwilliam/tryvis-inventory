from django.contrib import admin
from django.utils.html import format_html

from accounts.models import user_can_see_cost
from catalog.models import Category, Item, Supplier, UnitOfMeasure


@admin.register(UnitOfMeasure)
class UnitOfMeasureAdmin(admin.ModelAdmin):
    list_display = ("name", "abbreviation")
    search_fields = ("name", "abbreviation")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "item_count", "last_sequence")
    search_fields = ("name", "code")

    @admin.display(description="How many items")
    def item_count(self, obj):
        return obj.items.count()


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "country", "is_foreign", "is_active")
    list_filter = ("is_foreign", "is_active", "country")
    search_fields = ("name", "contact_person", "phone", "email")


@admin.register(Item)
class ItemAdmin(admin.ModelAdmin):
    list_display = (
        "code", "name", "part_number", "category", "item_type",
        "quantity_on_hand", "unit", "minimum_level", "stock_flag", "selling_price",
    )
    list_filter = ("item_type", "category", "is_active")
    search_fields = ("code", "name", "part_number", "barcode", "description")
    readonly_fields = ("code", "quantity_on_hand", "average_cost", "last_purchase_cost")
    autocomplete_fields = ("category", "unit")
    fieldsets = (
        ("What the item is", {"fields": ("code", "name", "part_number", "barcode", "description")}),
        ("How it is grouped", {"fields": ("category", "unit", "item_type", "location", "is_active")}),
        ("Stock levels", {"fields": ("quantity_on_hand", "minimum_level", "reorder_quantity")}),
        ("Money", {"fields": ("average_cost", "last_purchase_cost", "selling_price")}),
    )

    @admin.display(description="Stock")
    def stock_flag(self, obj):
        if not obj.tracks_stock:
            return "-"
        if obj.is_below_minimum:
            return format_html('<b style="color:#c0392b">RUNNING OUT</b>')
        return format_html('<span style="color:#27ae60">OK</span>')

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if user_can_see_cost(request.user):
            return fieldsets
        return tuple(
            (name, {**opts, "fields": tuple(
                f for f in opts["fields"] if f not in ("average_cost", "last_purchase_cost")
            )})
            for name, opts in fieldsets
        )

    def get_list_display(self, request):
        columns = super().get_list_display(request)
        if user_can_see_cost(request.user):
            return columns
        return tuple(c for c in columns if c != "selling_price") + ("selling_price",)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
