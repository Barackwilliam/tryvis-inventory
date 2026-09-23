from django import forms
from django.forms import inlineformset_factory

from purchasing.models import Purchase, PurchaseLine

BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}
LINE_INPUT = {"class": "form-control form-control-sm"}
LINE_SELECT = {"class": "form-select form-select-sm"}


class PurchaseForm(forms.ModelForm):
    class Meta:
        labels = {
            "supplier_invoice_no": "Supplier's invoice number",
            "purchase_date": "Date received",
            "currency": "Currency you paid in",
            "exchange_rate": "1 of that currency = how many TZS",
            "freight_cost": "Shipping",
            "customs_duty": "Customs",
            "clearing_charges": "Clearing",
            "other_charges": "Anything else",
            "allocation_method": "Share these extra costs",
        }
        model = Purchase
        fields = [
            "supplier", "supplier_invoice_no", "purchase_date", "currency", "exchange_rate",
            "freight_cost", "customs_duty", "clearing_charges", "other_charges",
            "allocation_method", "notes",
        ]
        widgets = {
            "supplier": forms.Select(attrs=BOOTSTRAP_SELECT),
            "supplier_invoice_no": forms.TextInput(attrs=BOOTSTRAP),
            "purchase_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "currency": forms.TextInput(attrs={**BOOTSTRAP, "maxlength": 3, "placeholder": "TZS"}),
            "exchange_rate": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.0001"}),
            "freight_cost": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "customs_duty": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "clearing_charges": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "other_charges": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "allocation_method": forms.Select(attrs=BOOTSTRAP_SELECT),
            "notes": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
        }

    def clean(self):
        cleaned = super().clean()
        currency = (cleaned.get("currency") or "TZS").upper()
        cleaned["currency"] = currency
        rate = cleaned.get("exchange_rate")
        if currency == "TZS" and rate and rate != 1:
            self.add_error("exchange_rate", "Put 1 here when you paid in TZS.")
        if currency != "TZS" and (not rate or rate <= 1):
            self.add_error("exchange_rate", "How many TZS is 1 of that currency worth?")
        return cleaned


class PurchaseLineForm(forms.ModelForm):
    class Meta:
        model = PurchaseLine
        fields = ["item", "quantity", "unit_price", "weight_kg"]

    def clean_quantity(self):
        quantity = self.cleaned_data.get("quantity")
        if quantity is not None and quantity <= 0:
            raise forms.ValidationError("How many did you receive? It cannot be zero.")
        return quantity


PurchaseLineFormSet = inlineformset_factory(
    Purchase,
    PurchaseLine,
    form=PurchaseLineForm,
    fields=["item", "quantity", "unit_price", "weight_kg"],
    widgets={
        "item": forms.Select(attrs=LINE_SELECT),
        "quantity": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.001"}),
        "unit_price": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.01"}),
        "weight_kg": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.001"}),
    },
    labels={"unit_price": "Price each", "weight_kg": "Weight kg"},
    extra=4,
    can_delete=True,
)
