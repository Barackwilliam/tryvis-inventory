from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from catalog.models import Item
from core.models import DocumentSequence, TimeStampedModel
from inventory.models import MovementType, record_movement
from sales.models import Customer


class JobStatus(models.TextChoices):
    OPEN = "OPEN", "Open"
    IN_PROGRESS = "IN_PROGRESS", "In progress"
    COMPLETED = "COMPLETED", "Completed"
    INVOICED = "INVOICED", "Invoiced"
    CANCELLED = "CANCELLED", "Cancelled"


class JobCard(TimeStampedModel):
    """
    A workshop job. Every part and consumable fitted on the job is issued
    from stock against this card, so at the end the company can compare what
    the job cost against what the customer was charged.
    """

    reference = models.CharField(max_length=40, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="jobs")
    title = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    equipment = models.CharField(
        max_length=160, blank=True, help_text="Which machine you are working on."
    )

    start_date = models.DateField(default=timezone.now)
    due_date = models.DateField(
        null=True, blank=True, help_text="When you promised it to the customer."
    )
    completed_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=JobStatus.choices, default=JobStatus.OPEN
    )

    labour_hours = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0")
    )
    labour_rate = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )
    other_costs = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Transport, hired tools, work given to someone else.",
    )
    quoted_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        help_text="What you are charging the customer for this job.",
    )

    class Meta:
        ordering = ["-start_date", "-id"]

    def __str__(self):
        return f"{self.reference} - {self.title}"

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = DocumentSequence.next_number("JOB", self.start_date.year)
        super().save(*args, **kwargs)

    # --- costing --------------------------------------------------------
    @property
    def is_open(self):
        return self.status in (JobStatus.OPEN, JobStatus.IN_PROGRESS)

    @property
    def is_overdue(self):
        return bool(self.due_date and self.is_open and self.due_date < timezone.now().date())

    @property
    def material_cost(self):
        return sum(
            (material.total_cost for material in self.materials.all()), Decimal("0")
        )

    @property
    def labour_cost(self):
        return self.labour_hours * self.labour_rate

    @property
    def total_cost(self):
        return self.material_cost + self.labour_cost + self.other_costs

    @property
    def profit(self):
        return self.quoted_amount - self.total_cost

    @property
    def margin_percent(self):
        if not self.quoted_amount:
            return None
        return self.profit / self.quoted_amount * 100


class JobMaterial(models.Model):
    """One part or consumable issued from the store to a job."""

    job = models.ForeignKey(JobCard, on_delete=models.PROTECT, related_name="materials")
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0"), editable=False
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    is_issued = models.BooleanField(default=False, editable=False)

    def __str__(self):
        return f"{self.item.code} x {self.quantity} on {self.job.reference}"

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost

    @transaction.atomic
    def issue(self, user=None):
        """Take the material out of stock at today's average cost."""
        if self.is_issued:
            raise ValueError("This material has already been issued.")

        movement = record_movement(
            item=self.item,
            movement_type=MovementType.JOB_ISSUE,
            quantity=self.quantity,
            movement_date=timezone.now().date(),
            source_document="JOB",
            source_reference=self.job.reference,
            user=user,
        )
        self.unit_cost = movement.unit_cost
        self.is_issued = True
        self.save(update_fields=["unit_cost", "is_issued"])
        return movement
