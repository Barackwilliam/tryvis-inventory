"""
This project owns its own users.

It runs on the same Supabase Postgres as the tryvis.co.tz website, but in its
own schema, so its auth tables are its own. That makes a custom user model the
clean choice: the role lives on the user itself, with no profile table to
join through and no signal to keep in step.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models


class Role(models.TextChoices):
    MANAGER = "MANAGER", "Manager"
    SHOPKEEPER = "SHOPKEEPER", "Shopkeeper"


class User(AbstractUser):
    """
    Manager     - everything: cost, margin, purchases, reports, settings.
    Shopkeeper  - receive stock, issue stock, quotations, invoices,
                  delivery notes, job cards. Cost and margin are hidden.
    """

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.SHOPKEEPER)
    phone = models.CharField(max_length=20, blank=True)
    receives_stock_alerts = models.BooleanField(
        default=False, help_text="Send this person the daily email about items running out."
    )

    class Meta:
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def is_manager(self):
        return self.role == Role.MANAGER or self.is_superuser

    @property
    def can_see_cost(self):
        """Cost price, margin and company-wide reports are Manager-only."""
        return self.is_manager


def user_is_manager(user):
    return bool(user and user.is_authenticated and user.is_manager)


def user_can_see_cost(user):
    return user_is_manager(user)
