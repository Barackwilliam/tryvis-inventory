from django import forms
from django.forms import inlineformset_factory

from sales.models import (
    Customer, DeliveryNote, DeliveryNoteLine, Invoice, InvoiceLine,
    Payment, Quotation, QuotationLine,
)

BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}
LINE_INPUT = {"class": "form-control form-control-sm"}
LINE_SELECT = {"class": "form-select form-select-sm"}


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["name", "contact_person", "phone", "email", "address", "tin", "vrn", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs=BOOTSTRAP),
            "contact_person": forms.TextInput(attrs=BOOTSTRAP),
            "phone": forms.TextInput(attrs=BOOTSTRAP),
            "email": forms.EmailInput(attrs=BOOTSTRAP),
            "address": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
            "tin": forms.TextInput(attrs=BOOTSTRAP),
            "vrn": forms.TextInput(attrs=BOOTSTRAP),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class QuotationForm(forms.ModelForm):
    class Meta:
        labels = {
            "document_date": "Date",
            "valid_until": "Price good until",
            "apply_vat": "Add VAT",
            "is_vat_inclusive": "Prices already include VAT",
        }
        model = Quotation
        fields = ["customer", "document_date", "valid_until", "apply_vat", "is_vat_inclusive", "notes"]
        widgets = {
            "customer": forms.Select(attrs=BOOTSTRAP_SELECT),
            "document_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "valid_until": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "apply_vat": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_vat_inclusive": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
        }


LINE_WIDGETS = {
    "item": forms.Select(attrs=LINE_SELECT),
    "description": forms.TextInput(attrs=LINE_INPUT),
    "quantity": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.001"}),
    "unit_price": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.01"}),
    "discount_percent": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.01"}),
}
LINE_FIELDS = ["item", "description", "quantity", "unit_price", "discount_percent"]
LINE_LABELS = {"unit_price": "Price each", "discount_percent": "Discount %"}

QuotationLineFormSet = inlineformset_factory(
    Quotation, QuotationLine, fields=LINE_FIELDS, widgets=LINE_WIDGETS,
    labels=LINE_LABELS, extra=4, can_delete=True
)
InvoiceLineFormSet = inlineformset_factory(
    Invoice, InvoiceLine, fields=LINE_FIELDS, widgets=LINE_WIDGETS,
    labels=LINE_LABELS, extra=2, can_delete=True
)
DeliveryNoteLineFormSet = inlineformset_factory(
    DeliveryNote, DeliveryNoteLine, fields=LINE_FIELDS, widgets=LINE_WIDGETS,
    labels=LINE_LABELS, extra=2, can_delete=True
)


class InvoiceForm(forms.ModelForm):
    class Meta:
        labels = {
            "document_date": "Date",
            "due_date": "Customer should pay by",
            "apply_vat": "Add VAT",
            "is_vat_inclusive": "Prices already include VAT",
        }
        model = Invoice
        fields = ["customer", "document_date", "due_date", "apply_vat", "is_vat_inclusive", "notes"]
        widgets = {
            "customer": forms.Select(attrs=BOOTSTRAP_SELECT),
            "document_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "due_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "apply_vat": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_vat_inclusive": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notes": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
        }


class DeliveryNoteForm(forms.ModelForm):
    class Meta:
        labels = {
            "document_date": "Date",
            "delivered_to": "Who received it",
            "vehicle_number": "Vehicle number",
        }
        model = DeliveryNote
        fields = ["customer", "document_date", "delivered_to", "vehicle_number", "notes"]
        widgets = {
            "customer": forms.Select(attrs=BOOTSTRAP_SELECT),
            "document_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "delivered_to": forms.TextInput(attrs=BOOTSTRAP),
            "vehicle_number": forms.TextInput(attrs=BOOTSTRAP),
            "notes": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
        }


class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["amount", "paid_on", "method", "reference"]
        labels = {
            "amount": "How much did they pay",
            "paid_on": "Date",
            "method": "How they paid",
            "reference": "Receipt number (optional)",
        }
        widgets = {
            "amount": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "paid_on": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "method": forms.Select(attrs=BOOTSTRAP_SELECT),
            "reference": forms.TextInput(attrs=BOOTSTRAP),
        }
