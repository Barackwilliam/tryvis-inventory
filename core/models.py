"""
Shared building blocks used across the Tryvis Inventory System.
"""
from django.conf import settings
from django.db import models, transaction


class TimeStampedModel(models.Model):
    """Every business record knows when it was created and by whom."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="%(class)s_created",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class DocumentSequence(models.Model):
    """
    Gives out gap-free document numbers such as QTN-2026-0001.

    One row per (prefix, year). Locked with select_for_update so two users
    saving at the same moment can never receive the same number.
    """

    prefix = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last_number = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("prefix", "year")

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.last_number}"

    @classmethod
    @transaction.atomic
    def next_number(cls, prefix, year, padding=4):
        sequence, _ = cls.objects.select_for_update().get_or_create(
            prefix=prefix, year=year
        )
        sequence.last_number += 1
        sequence.save(update_fields=["last_number"])
        return f"{prefix}-{year}-{str(sequence.last_number).zfill(padding)}"
