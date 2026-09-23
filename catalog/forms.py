from django import forms

from catalog.models import Category, Item, Supplier, UnitOfMeasure

BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}


class ItemForm(forms.ModelForm):
    class Meta:
        labels = {
            "name": "Item name",
            "part_number": "Part number on the item",
            "category": "Group",
            "unit": "Sold by",
            "item_type": "What kind of item",
            "minimum_level": "Warn me when stock drops to",
            "reorder_quantity": "Order this many at a time",
            "selling_price": "Price each",
            "location": "Where it is kept",
            "is_active": "Still in use",
        }
        model = Item
        fields = [
            "name", "part_number", "barcode", "description", "category", "unit",
            "item_type", "minimum_level", "reorder_quantity", "selling_price",
            "location", "is_active",
        ]
        widgets = {
            "name": forms.TextInput(attrs=BOOTSTRAP),
            "part_number": forms.TextInput(attrs={**BOOTSTRAP, "placeholder": "e.g. 6204"}),
            "barcode": forms.TextInput(attrs=BOOTSTRAP),
            "description": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
            "category": forms.Select(attrs=BOOTSTRAP_SELECT),
            "unit": forms.Select(attrs=BOOTSTRAP_SELECT),
            "item_type": forms.Select(attrs=BOOTSTRAP_SELECT),
            "minimum_level": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.001"}),
            "reorder_quantity": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.001"}),
            "selling_price": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "location": forms.TextInput(attrs={**BOOTSTRAP, "placeholder": "Shelf / rack"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class CategoryForm(forms.ModelForm):
    class Meta:
        labels = {"name": "Group name", "code": "Three-letter code"}
        model = Category
        fields = ["name", "code", "description"]
        widgets = {
            "name": forms.TextInput(attrs=BOOTSTRAP),
            "code": forms.TextInput(attrs={**BOOTSTRAP, "placeholder": "BRG", "maxlength": 4}),
            "description": forms.TextInput(attrs=BOOTSTRAP),
        }


class SupplierForm(forms.ModelForm):
    class Meta:
        labels = {
            "name": "Supplier name",
            "contact_person": "Person you talk to",
            "is_foreign": "Goods come from outside Tanzania",
            "is_active": "Still buying from them",
        }
        model = Supplier
        fields = ["name", "contact_person", "phone", "email", "address", "country", "is_foreign", "is_active"]
        widgets = {
            "name": forms.TextInput(attrs=BOOTSTRAP),
            "contact_person": forms.TextInput(attrs=BOOTSTRAP),
            "phone": forms.TextInput(attrs=BOOTSTRAP),
            "email": forms.EmailInput(attrs=BOOTSTRAP),
            "address": forms.Textarea(attrs={**BOOTSTRAP, "rows": 2}),
            "country": forms.TextInput(attrs=BOOTSTRAP),
            "is_foreign": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class UnitForm(forms.ModelForm):
    class Meta:
        labels = {"name": "Unit name", "abbreviation": "Short form"}
        model = UnitOfMeasure
        fields = ["name", "abbreviation"]
        widgets = {
            "name": forms.TextInput(attrs=BOOTSTRAP),
            "abbreviation": forms.TextInput(attrs=BOOTSTRAP),
        }
