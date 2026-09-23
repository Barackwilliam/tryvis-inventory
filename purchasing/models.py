from decimal import Decimal

from django.db import models, transaction
from django.utils import timezone

from catalog.models import Item, Supplier
from core.models import DocumentSequence, TimeStampedModel
from inventory.models import MovementType, record_movement


class AllocationMethod(models.TextChoices):
    BY_VALUE = "BY_VALUE", "By price - dearer items carry more"
    BY_QUANTITY = "BY_QUANTITY", "By quantity - each piece the same"
    BY_WEIGHT = "BY_WEIGHT", "By weight - heavier items carry more"


class PurchaseStatus(models.TextChoices):
    DRAFT = "DRAFT", "Not added yet"
    RECEIVED = "RECEIVED", "Added to the store"
    CANCELLED = "CANCELLED", "Cancelled"


class Purchase(TimeStampedModel):
    """
    A goods received note (GRN).

    For imported goods the invoice price is only part of the truth. Freight,
    customs duty, clearing and any other charge are entered on the header and
    spread across the lines, so `landed_unit_cost` is the real cost of one
    piece sitting on the shelf. That figure, not the supplier price, is what
    every profit calculation in the system uses.
    """

    reference = models.CharField(max_length=40, unique=True, editable=False)
    supplier = models.ForeignKey(
        Supplier, on_delete=models.PROTECT, related_name="purchases"
    )
    supplier_invoice_no = models.CharField(max_length=60, blank=True)
    purchase_date = models.DateField(default=timezone.now)

    currency = models.CharField(max_length=3, default="TZS")
    exchange_rate = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        default=Decimal("1"),
        help_text="How many TZS for 1 of that currency. Put 1 if you paid in TZS.",
    )

    freight_cost = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )
    customs_duty = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )
    clearing_charges = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )
    other_charges = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )
    allocation_method = models.CharField(
        max_length=20,
        choices=AllocationMethod.choices,
        default=AllocationMethod.BY_VALUE,
    )

    status = models.CharField(
        max_length=20, choices=PurchaseStatus.choices, default=PurchaseStatus.DRAFT
    )
    received_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-purchase_date", "-id"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = DocumentSequence.next_number(
                "GRN", self.purchase_date.year
            )
        super().save(*args, **kwargs)

    # --- totals ---------------------------------------------------------
    @property
    def goods_total_tzs(self):
        return sum((line.line_total_tzs for line in self.lines.all()), Decimal("0"))

    @property
    def additional_charges(self):
        return (
            self.freight_cost
            + self.customs_duty
            + self.clearing_charges
            + self.other_charges
        )

    @property
    def landed_total(self):
        return self.goods_total_tzs + self.additional_charges

    # --- receiving ------------------------------------------------------
    @transaction.atomic
    def receive(self, user=None):
        """Allocate charges, cost every line, then push the stock in."""
        if self.status == PurchaseStatus.RECEIVED:
            raise ValueError(f"{self.reference} has already been received.")

        lines = list(self.lines.select_related("item"))
        if not lines:
            raise ValueError("Add at least one item before adding this to the store.")

        empty = [line for line in lines if line.quantity <= 0]
        if empty:
            raise ValueError(
                "Every line needs a quantity greater than zero. Check: "
                + ", ".join(line.item.code for line in empty)
            )

        charges = self.additional_charges
        basis_total = sum((line.allocation_basis(self.allocation_method) for line in lines), Decimal("0"))

        allocated_so_far = Decimal("0")
        for index, line in enumerate(lines):
            if charges and basis_total:
                if index == len(lines) - 1:
                    # last line absorbs the rounding remainder, so the charges
                    # entered always equal the charges spread across the goods
                    line.allocated_charges = charges - allocated_so_far
                else:
                    share = line.allocation_basis(self.allocation_method) / basis_total
                    line.allocated_charges = (charges * share).quantize(Decimal("0.01"))
                    allocated_so_far += line.allocated_charges
            else:
                line.allocated_charges = Decimal("0")
            line.landed_unit_cost = (
                (line.line_total_tzs + line.allocated_charges) / line.quantity
            ).quantize(Decimal("0.01"))
            line.save(update_fields=["allocated_charges", "landed_unit_cost"])

            record_movement(
                item=line.item,
                movement_type=MovementType.PURCHASE_IN,
                quantity=line.quantity,
                unit_cost=line.landed_unit_cost,
                movement_date=self.purchase_date,
                source_document="GRN",
                source_reference=self.reference,
                user=user,
            )

        self.status = PurchaseStatus.RECEIVED
        self.received_at = timezone.now()
        self.save(update_fields=["status", "received_at"])
        return self


class PurchaseLine(models.Model):
    purchase = models.ForeignKey(
        Purchase, on_delete=models.CASCADE, related_name="lines"
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        help_text="The supplier's price for one piece, in the currency you paid.",
    )
    weight_kg = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        default=Decimal("0"),
        help_text="Only needed if you share the extra costs by weight.",
    )

    allocated_charges = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0"), editable=False
    )
    landed_unit_cost = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0"), editable=False
    )

    def __str__(self):
        return f"{self.item.code} x {self.quantity}"

    @property
    def line_total_tzs(self):
        return self.quantity * self.unit_price * self.purchase.exchange_rate

    def allocation_basis(self, method):
        if method == AllocationMethod.BY_QUANTITY:
            return self.quantity
        if method == AllocationMethod.BY_WEIGHT:
            return self.weight_kg
        return self.line_total_tzs
