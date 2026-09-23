from django.contrib import admin, messages

from sales.models import (
    Customer, DeliveryNote, DeliveryNoteLine, Invoice, InvoiceLine,
    Payment, Quotation, QuotationLine,
)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_person", "phone", "email", "tin", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_person", "phone", "email", "tin")


class QuotationLineInline(admin.TabularInline):
    model = QuotationLine
    extra = 3
    autocomplete_fields = ("item",)


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 1


class InvoiceLineInline(admin.TabularInline):
    model = InvoiceLine
    extra = 3
    autocomplete_fields = ("item",)


class DeliveryNoteLineInline(admin.TabularInline):
    model = DeliveryNoteLine
    extra = 3
    autocomplete_fields = ("item",)


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "document_date", "valid_until", "status", "grand_total")
    list_filter = ("status", "document_date")
    search_fields = ("reference", "customer__name")
    readonly_fields = ("reference",)
    autocomplete_fields = ("customer",)
    inlines = [QuotationLineInline]
    actions = ["convert_selected"]

    @admin.action(description="Turn into an invoice")
    def convert_selected(self, request, queryset):
        for quotation in queryset:
            try:
                invoice = quotation.convert_to_invoice(user=request.user)
                self.message_user(request, f"{quotation.reference} -> {invoice.reference}", messages.SUCCESS)
            except Exception as exc:
                self.message_user(request, f"{quotation.reference}: {exc}", messages.ERROR)


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "document_date", "due_date", "status", "grand_total", "balance_due")
    list_filter = ("status", "document_date")
    search_fields = ("reference", "customer__name")
    readonly_fields = ("reference", "quotation")
    autocomplete_fields = ("customer",)
    inlines = [InvoiceLineInline, PaymentInline]
    actions = ["raise_delivery_note"]

    @admin.action(description="Make a delivery note")
    def raise_delivery_note(self, request, queryset):
        for invoice in queryset:
            note = invoice.create_delivery_note(user=request.user)
            self.message_user(request, f"{invoice.reference} -> {note.reference}", messages.SUCCESS)


@admin.register(DeliveryNote)
class DeliveryNoteAdmin(admin.ModelAdmin):
    list_display = ("reference", "customer", "document_date", "status", "delivered_to", "vehicle_number")
    list_filter = ("status", "document_date")
    search_fields = ("reference", "customer__name", "delivered_to")
    readonly_fields = ("reference", "delivered_at")
    autocomplete_fields = ("customer",)
    inlines = [DeliveryNoteLineInline]
    actions = ["confirm_selected"]

    @admin.action(description="Confirm the customer took the goods")
    def confirm_selected(self, request, queryset):
        for note in queryset:
            try:
                note.confirm_delivery(user=request.user)
                self.message_user(request, f"{note.reference}: goods have left the store.", messages.SUCCESS)
            except Exception as exc:
                self.message_user(request, f"{note.reference}: {exc}", messages.ERROR)
