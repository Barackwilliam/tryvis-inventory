from decimal import Decimal

from django import forms

from catalog.models import Item, ItemType
from inventory.models import MovementType

BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}

ADJUSTMENT_CHOICES = [
    (MovementType.OPENING, "Starting stock - first time entering this item"),
    (MovementType.ADJUSTMENT_IN, "I counted and found more than the system says"),
    (MovementType.ADJUSTMENT_OUT, "I counted and found less than the system says"),
    (MovementType.RETURN_IN, "Customer brought something back"),
    (MovementType.RETURN_OUT, "We sent something back to the supplier"),
]


class StockAdjustmentForm(forms.Form):
    """Manual correction outside the purchase / sales flow."""

    item = forms.ModelChoiceField(
        queryset=Item.objects.filter(
            is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
        ),
        widget=forms.Select(attrs={**BOOTSTRAP_SELECT, "data-search": "true"}),
    )
    movement_type = forms.ChoiceField(
        label="What happened",
        choices=ADJUSTMENT_CHOICES,
        widget=forms.Select(attrs=BOOTSTRAP_SELECT),
    )
    quantity = forms.DecimalField(
        label="How many",
        min_value=Decimal("0.001"), decimal_places=3,
        widget=forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.001"}),
    )
    unit_cost = forms.DecimalField(
        required=False, min_value=Decimal("0"), decimal_places=2,
        label="Cost of one piece",
        help_text="Only needed when you are adding stock, not removing it.",
        widget=forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
    )
    movement_date = forms.DateField(
        label="Date",
        widget=forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
    )
    notes = forms.CharField(
        label="Reason (optional)",
        max_length=200, required=False, widget=forms.TextInput(attrs=BOOTSTRAP),
    )

    def clean(self):
        cleaned = super().clean()
        movement_type = cleaned.get("movement_type")
        item = cleaned.get("item")
        quantity = cleaned.get("quantity")
        if movement_type in (MovementType.ADJUSTMENT_OUT, MovementType.RETURN_OUT):
            if item and quantity and quantity > item.quantity_on_hand:
                raise forms.ValidationError(
                    f"There are only {item.quantity_on_hand} {item.unit} of {item.code} in the store."
                )
        if movement_type in (MovementType.OPENING, MovementType.ADJUSTMENT_IN):
            if not cleaned.get("unit_cost") and item and not item.average_cost:
                raise forms.ValidationError(
                    "Please enter what one piece costs. The system has no cost for this item yet."
                )
        return cleaned
