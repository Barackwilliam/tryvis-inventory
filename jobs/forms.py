from django import forms
from django.forms import inlineformset_factory

from jobs.models import JobCard, JobMaterial

BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}
LINE_INPUT = {"class": "form-control form-control-sm"}
LINE_SELECT = {"class": "form-select form-select-sm"}


class JobCardForm(forms.ModelForm):
    class Meta:
        labels = {
            "title": "What is the job",
            "equipment": "Machine being worked on",
            "start_date": "Started on",
            "due_date": "Promised to customer by",
            "completed_date": "Finished on",
            "labour_hours": "Hours worked",
            "labour_rate": "Price per hour",
            "other_costs": "Other costs",
            "quoted_amount": "What you charge the customer",
        }
        model = JobCard
        fields = [
            "customer", "title", "equipment", "description", "start_date",
            "due_date", "completed_date", "status", "labour_hours", "labour_rate",
            "other_costs", "quoted_amount",
        ]
        widgets = {
            "customer": forms.Select(attrs=BOOTSTRAP_SELECT),
            "title": forms.TextInput(attrs=BOOTSTRAP),
            "equipment": forms.TextInput(attrs=BOOTSTRAP),
            "description": forms.Textarea(attrs={**BOOTSTRAP, "rows": 3}),
            "start_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "due_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "completed_date": forms.DateInput(attrs={**BOOTSTRAP, "type": "date"}),
            "status": forms.Select(attrs=BOOTSTRAP_SELECT),
            "labour_hours": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.25"}),
            "labour_rate": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "other_costs": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
            "quoted_amount": forms.NumberInput(attrs={**BOOTSTRAP, "step": "0.01"}),
        }


JobMaterialFormSet = inlineformset_factory(
    JobCard,
    JobMaterial,
    fields=["item", "quantity"],
    widgets={
        "item": forms.Select(attrs=LINE_SELECT),
        "quantity": forms.NumberInput(attrs={**LINE_INPUT, "step": "0.001"}),
    },
    extra=4,
    can_delete=True,
)
