from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm

from accounts.models import Role

User = get_user_model()
BOOTSTRAP = {"class": "form-control"}
BOOTSTRAP_SELECT = {"class": "form-select"}


class UserCreateForm(forms.ModelForm):
    """Adding a person to the system, with their first password."""

    password1 = forms.CharField(
        label="Password", widget=forms.PasswordInput(attrs=BOOTSTRAP), min_length=8,
        help_text="At least 8 characters. They can change it after signing in.",
    )
    password2 = forms.CharField(
        label="Type the password again", widget=forms.PasswordInput(attrs=BOOTSTRAP)
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "phone",
                  "role", "receives_stock_alerts"]
        labels = {
            "username": "Username they will sign in with",
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email",
            "phone": "Phone",
            "role": "What they can do",
            "receives_stock_alerts": "Email them when items run out",
        }
        help_texts = {
            "role": "A Manager sees costs, profit and reports. A Shopkeeper does not.",
            "email": "Needed if they should get the daily email about items running out.",
        }
        widgets = {
            "username": forms.TextInput(attrs=BOOTSTRAP),
            "first_name": forms.TextInput(attrs=BOOTSTRAP),
            "last_name": forms.TextInput(attrs=BOOTSTRAP),
            "email": forms.EmailInput(attrs=BOOTSTRAP),
            "phone": forms.TextInput(attrs=BOOTSTRAP),
            "role": forms.Select(attrs=BOOTSTRAP_SELECT),
            "receives_stock_alerts": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password1") != cleaned.get("password2"):
            self.add_error("password2", "The two passwords are not the same.")
        if cleaned.get("receives_stock_alerts") and not cleaned.get("email"):
            self.add_error("email", "Add an email address, or untick the email option.")
        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserEditForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "phone", "role",
                  "receives_stock_alerts", "is_active"]
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "email": "Email",
            "phone": "Phone",
            "role": "What they can do",
            "receives_stock_alerts": "Email them when items run out",
            "is_active": "Can sign in",
        }
        help_texts = {
            "is_active": "Untick instead of deleting. Their past work stays in the records.",
        }
        widgets = {
            "first_name": forms.TextInput(attrs=BOOTSTRAP),
            "last_name": forms.TextInput(attrs=BOOTSTRAP),
            "email": forms.EmailInput(attrs=BOOTSTRAP),
            "phone": forms.TextInput(attrs=BOOTSTRAP),
            "role": forms.Select(attrs=BOOTSTRAP_SELECT),
            "receives_stock_alerts": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, editing_self=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.editing_self = editing_self
        if editing_self:
            # Nobody gets to lock themselves out of their own system.
            self.fields["role"].disabled = True
            self.fields["is_active"].disabled = True
            self.fields["role"].help_text = "You cannot change your own role."
            self.fields["is_active"].help_text = "You cannot switch off your own account."

    def clean(self):
        cleaned = super().clean()
        if self.editing_self:
            cleaned["role"] = self.instance.role
            cleaned["is_active"] = True
        if cleaned.get("receives_stock_alerts") and not cleaned.get("email"):
            self.add_error("email", "Add an email address, or untick the email option.")
        return cleaned


class ManagerSetPasswordForm(SetPasswordForm):
    """Manager sets a new password for someone who forgot theirs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update(BOOTSTRAP)
        self.fields["new_password1"].label = "New password"
        self.fields["new_password2"].label = "Type it again"
