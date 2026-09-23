from decimal import Decimal

from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from catalog.models import Item
from core.models import TimeStampedModel


class MovementType(models.TextChoices):
    PURCHASE_IN = "PURCHASE_IN", "Bought - added to store"
    SALE_OUT = "SALE_OUT", "Sold - given to customer"
    JOB_ISSUE = "JOB_ISSUE", "Used on a workshop job"
    RETURN_IN = "RETURN_IN", "Customer brought it back"
    RETURN_OUT = "RETURN_OUT", "Sent back to supplier"
    ADJUSTMENT_IN = "ADJUSTMENT_IN", "Counted - found more"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT", "Counted - found less"
    OPENING = "OPENING", "Starting stock"


INWARD_TYPES = {
    MovementType.PURCHASE_IN,
    MovementType.RETURN_IN,
    MovementType.ADJUSTMENT_IN,
    MovementType.OPENING,
}


class StockMovementQuerySet(models.QuerySet):
    def inward(self):
        return self.filter(movement_type__in=INWARD_TYPES)

    def outward(self):
        return self.exclude(movement_type__in=INWARD_TYPES)

    def balance_for(self, item):
        rows = self.filter(item=item)
        received = rows.inward().aggregate(t=Sum("quantity"))["t"] or Decimal("0")
        issued = rows.outward().aggregate(t=Sum("quantity"))["t"] or Decimal("0")
        return received - issued

    def sold_between(self, start, end):
        """Quantity sold per item - the basis of fast / slow moving reports."""
        return (
            self.filter(
                movement_type=MovementType.SALE_OUT,
                movement_date__range=(start, end),
            )
            .values("item")
            .annotate(quantity_sold=Sum("quantity"))
        )


class StockMovement(TimeStampedModel):
    """
    The single source of truth for stock. Nothing changes `quantity_on_hand`
    except a row landing here. Rows are never edited or deleted - a mistake is
    corrected with an opposite movement, so the history always stays auditable.
    """

    item = models.ForeignKey(Item, on_delete=models.PROTECT, related_name="movements")
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0"),
        help_text="What one piece cost us at that moment, in TZS.",
    )
    movement_date = models.DateField(default=timezone.now)

    # Where the movement came from, e.g. ("GRN", "GRN-2026-0007")
    source_document = models.CharField(max_length=20, blank=True)
    source_reference = models.CharField(max_length=40, blank=True, db_index=True)

    balance_after = models.DecimalField(
        max_digits=14, decimal_places=3, default=Decimal("0"), editable=False
    )
    notes = models.CharField(max_length=200, blank=True)

    objects = StockMovementQuerySet.as_manager()

    class Meta:
        ordering = ["-movement_date", "-id"]
        indexes = [
            models.Index(fields=["item", "movement_date"]),
            models.Index(fields=["movement_type", "movement_date"]),
        ]

    def __str__(self):
        sign = "+" if self.is_inward else "-"
        return f"{self.item.code} {sign}{self.quantity} ({self.get_movement_type_display()})"

    @property
    def is_inward(self):
        return self.movement_type in INWARD_TYPES

    @property
    def value(self):
        return self.quantity * self.unit_cost


@transaction.atomic
def record_movement(
    *,
    item,
    movement_type,
    quantity,
    unit_cost=None,
    movement_date=None,
    source_document="",
    source_reference="",
    notes="",
    user=None,
    allow_negative=False,
):
    """
    The one function every other app calls to move stock.

    Inward movements update the weighted average cost:

        new_average = (existing_value + incoming_value) / (existing_qty + incoming_qty)

    Outward movements leave the average alone and are costed at the current
    average, which is what makes the profit figure on an invoice meaningful.
    """
    if quantity is None or Decimal(quantity) <= 0:
        raise ValueError("Quantity must be greater than zero.")

    quantity = Decimal(quantity)
    item = Item.objects.select_for_update().get(pk=item.pk)

    if not item.tracks_stock:
        raise ValueError(f"{item.code} is a service, so there is no stock to move.")

    inward = movement_type in INWARD_TYPES

    if inward:
        cost = Decimal(unit_cost if unit_cost is not None else item.average_cost)
        existing_value = item.quantity_on_hand * item.average_cost
        incoming_value = quantity * cost
        new_quantity = item.quantity_on_hand + quantity
        if new_quantity > 0:
            item.average_cost = (existing_value + incoming_value) / new_quantity
        if movement_type == MovementType.PURCHASE_IN:
            item.last_purchase_cost = cost
        item.quantity_on_hand = new_quantity
    else:
        cost = Decimal(unit_cost if unit_cost is not None else item.average_cost)
        new_quantity = item.quantity_on_hand - quantity
        if new_quantity < 0 and not allow_negative:
            raise ValueError(
                f"Not enough {item.code} in the store. "
                f"There are {item.quantity_on_hand}, but {quantity} was asked for."
            )
        item.quantity_on_hand = new_quantity

    item.save(
        update_fields=["quantity_on_hand", "average_cost", "last_purchase_cost"]
    )

    return StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        unit_cost=cost,
        movement_date=movement_date or timezone.now().date(),
        source_document=source_document,
        source_reference=source_reference,
        balance_after=item.quantity_on_hand,
        notes=notes,
        created_by=user,
    )


class Briefing(models.Model):
    """
    A written briefing, kept against a fingerprint of the numbers it describes.

    Caching on the facts rather than on a clock means the text is regenerated
    the moment the business changes, and not once in between.
    """

    SOURCES = [("grok", "Written by Grok"), ("system", "Written by the system")]

    fingerprint = models.CharField(max_length=32, unique=True, db_index=True)
    text = models.TextField()
    source = models.CharField(max_length=10, choices=SOURCES, default="system")
    facts = models.JSONField(
        default=dict, help_text="Exactly the figures the text was written from."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Briefing {self.created_at:%d %b %H:%M} ({self.source})"

    @property
    def paragraphs(self):
        return [p.strip() for p in self.text.split("\n") if p.strip()]


class StockAlertLog(models.Model):
    """
    Remembers that an item was already reported, so the daily email does not
    nag about the same item every morning until it is restocked.
    """

    item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="alerts")
    quantity_at_alert = models.DecimalField(max_digits=14, decimal_places=3)
    minimum_at_alert = models.DecimalField(max_digits=14, decimal_places=3)
    sent_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]

    def __str__(self):
        return f"{self.item.code} low stock alert {self.sent_at:%Y-%m-%d}"
