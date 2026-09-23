from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from catalog.models import Item
from core.models import DocumentSequence, TimeStampedModel
from inventory.models import MovementType, record_movement

# Tanzania standard rate, overridable with VAT_RATE_PERCENT
VAT_RATE = Decimal(str(getattr(settings, "VAT_RATE_PERCENT", "18"))) / 100


class Customer(TimeStampedModel):
    name = models.CharField(max_length=140, unique=True)
    contact_person = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    tin = models.CharField(max_length=20, blank=True, verbose_name="TIN")
    vrn = models.CharField(max_length=20, blank=True, verbose_name="VRN")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class SalesDocument(TimeStampedModel):
    """Shared fields for quotations, invoices and delivery notes."""

    PREFIX = "DOC"

    reference = models.CharField(max_length=40, unique=True, editable=False)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    document_date = models.DateField(default=timezone.now)
    is_vat_inclusive = models.BooleanField(default=False)
    apply_vat = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ["-document_date", "-id"]

    def __str__(self):
        return self.reference

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = DocumentSequence.next_number(
                self.PREFIX, self.document_date.year
            )
        super().save(*args, **kwargs)

    @property
    def subtotal(self):
        return sum((line.line_total for line in self.lines.all()), Decimal("0"))

    @property
    def vat_amount(self):
        if not self.apply_vat:
            return Decimal("0")
        if self.is_vat_inclusive:
            return (self.subtotal * VAT_RATE / (1 + VAT_RATE)).quantize(Decimal("0.01"))
        return (self.subtotal * VAT_RATE).quantize(Decimal("0.01"))

    @property
    def grand_total(self):
        if self.is_vat_inclusive or not self.apply_vat:
            return self.subtotal
        return self.subtotal + self.vat_amount


class SalesLine(models.Model):
    """Shared fields for the lines of every sales document."""

    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    description = models.CharField(
        max_length=200,
        blank=True,
        help_text="Use this if you want different wording on the printed paper.",
    )
    quantity = models.DecimalField(max_digits=14, decimal_places=3)
    unit_price = models.DecimalField(max_digits=16, decimal_places=2)
    discount_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0")
    )

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.item.code} x {self.quantity}"

    @property
    def line_total(self):
        gross = self.quantity * self.unit_price
        return gross - (gross * self.discount_percent / 100)


# --------------------------------------------------------------------------
# 1. Quotation
# --------------------------------------------------------------------------
class QuotationStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SENT = "SENT", "Sent to customer"
    ACCEPTED = "ACCEPTED", "Accepted"
    INVOICED = "INVOICED", "Turned into an invoice"
    REJECTED = "REJECTED", "Rejected"
    EXPIRED = "EXPIRED", "Expired"


class Quotation(SalesDocument):
    PREFIX = "QTN"

    valid_until = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=QuotationStatus.choices, default=QuotationStatus.DRAFT
    )

    @transaction.atomic
    def convert_to_invoice(self, user=None):
        """Copy the quotation onto a fresh invoice. Stock is untouched here."""
        if self.status == QuotationStatus.INVOICED:
            raise ValueError(f"{self.reference} has already been invoiced.")

        invoice = Invoice.objects.create(
            customer=self.customer,
            document_date=timezone.now().date(),
            apply_vat=self.apply_vat,
            is_vat_inclusive=self.is_vat_inclusive,
            quotation=self,
            notes=self.notes,
            created_by=user,
        )
        InvoiceLine.objects.bulk_create(
            [
                InvoiceLine(
                    invoice=invoice,
                    item=line.item,
                    description=line.description,
                    quantity=line.quantity,
                    unit_price=line.unit_price,
                    discount_percent=line.discount_percent,
                )
                for line in self.lines.all()
            ]
        )
        self.status = QuotationStatus.INVOICED
        self.save(update_fields=["status"])
        return invoice


class QuotationLine(SalesLine):
    quotation = models.ForeignKey(
        Quotation, on_delete=models.CASCADE, related_name="lines"
    )


# --------------------------------------------------------------------------
# 2. Invoice
# --------------------------------------------------------------------------
class InvoiceStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    ISSUED = "ISSUED", "Issued"
    PART_PAID = "PART_PAID", "Part paid"
    PAID = "PAID", "Paid"
    CANCELLED = "CANCELLED", "Cancelled"


class Invoice(SalesDocument):
    PREFIX = "INV"

    quotation = models.OneToOneField(
        Quotation,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="invoice",
    )
    due_date = models.DateField(null=True, blank=True)

    # EFD / fiscal device fields
    # efd_receipt_number: typed by the user after printing the EFD receipt
    # efd_qr_image: uploaded as a base64 data-URL via the browser (no file storage needed)
    efd_receipt_number = models.CharField(max_length=50, blank=True, default="")
    efd_qr_image = models.TextField(blank=True, default="")  # base64 data-URL
    status = models.CharField(
        max_length=20, choices=InvoiceStatus.choices, default=InvoiceStatus.DRAFT
    )
    amount_paid = models.DecimalField(
        max_digits=16, decimal_places=2, default=Decimal("0")
    )

    @property
    def balance_due(self):
        return self.grand_total - self.amount_paid

    @property
    def is_overdue(self):
        from django.utils import timezone as tz

        return bool(
            self.due_date
            and self.balance_due > 0
            and self.status not in (InvoiceStatus.PAID, InvoiceStatus.CANCELLED)
            and self.due_date < tz.now().date()
        )

    def refresh_totals(self):
        """Re-add the payment rows and move the status to match."""
        total = self.payments.aggregate(t=models.Sum("amount"))["t"] or Decimal("0")
        self.amount_paid = total
        if self.status != InvoiceStatus.CANCELLED:
            if total <= 0:
                if self.status in (InvoiceStatus.PAID, InvoiceStatus.PART_PAID):
                    self.status = InvoiceStatus.ISSUED
            elif total >= self.grand_total:
                self.status = InvoiceStatus.PAID
            else:
                self.status = InvoiceStatus.PART_PAID
        self.save(update_fields=["amount_paid", "status"])

    @property
    def cost_of_sale(self):
        """Manager-only figure: what these goods actually cost the company."""
        return sum(
            (line.quantity * line.item.average_cost for line in self.lines.all()),
            Decimal("0"),
        )

    @property
    def gross_profit(self):
        return self.subtotal - self.cost_of_sale

    @property
    def has_been_delivered(self):
        return self.delivery_notes.filter(status=DeliveryStatus.DELIVERED).exists()

    @transaction.atomic
    def create_delivery_note(self, user=None):
        """
        Stock leaves the store here, not on the invoice. An invoice can be
        raised days before the goods are collected, and the ledger should
        reflect what physically happened.

        Only one delivery per invoice. Without this guard a second note takes
        the same goods out of stock a second time, and the shelf count drifts
        away from reality with nothing in the ledger looking wrong.
        """
        if self.has_been_delivered:
            raise ValueError(
                f"{self.reference} has already been delivered. "
                f"To send more goods, raise a new invoice."
            )
        open_note = self.delivery_notes.filter(status=DeliveryStatus.DRAFT).first()
        if open_note:
            return open_note

        note = DeliveryNote.objects.create(
            customer=self.customer,
            document_date=timezone.now().date(),
            invoice=self,
            apply_vat=self.apply_vat,
            is_vat_inclusive=self.is_vat_inclusive,
            created_by=user,
        )
        for line in self.lines.select_related("item"):
            DeliveryNoteLine.objects.create(
                delivery_note=note,
                item=line.item,
                description=line.description,
                quantity=line.quantity,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
            )
        return note


class InvoiceLine(SalesLine):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")


class PaymentMethod(models.TextChoices):
    CASH = "CASH", "Cash"
    BANK = "BANK", "Bank transfer"
    MOBILE = "MOBILE", "Mobile money"
    CHEQUE = "CHEQUE", "Cheque"


class Payment(TimeStampedModel):
    """
    One row per payment the customer actually makes.

    Invoice.amount_paid on its own carries no date, so it can never answer
    "how much came in this month". These rows can, and they also give the
    manager a history instead of a single moving number.
    """

    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=16, decimal_places=2)
    paid_on = models.DateField(default=timezone.now)
    method = models.CharField(
        max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH
    )
    reference = models.CharField(max_length=60, blank=True, help_text="Receipt or transfer number.")

    class Meta:
        ordering = ["-paid_on", "-id"]

    def __str__(self):
        return f"{self.invoice.reference}: {self.amount}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.invoice.refresh_totals()

    def delete(self, *args, **kwargs):
        invoice = self.invoice
        super().delete(*args, **kwargs)
        invoice.refresh_totals()


# --------------------------------------------------------------------------
# 3. Delivery note
# --------------------------------------------------------------------------
class DeliveryStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    DELIVERED = "DELIVERED", "Customer took the goods"
    CANCELLED = "CANCELLED", "Cancelled"


class DeliveryNote(SalesDocument):
    PREFIX = "DN"

    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="delivery_notes",
    )
    status = models.CharField(
        max_length=20, choices=DeliveryStatus.choices, default=DeliveryStatus.DRAFT
    )
    delivered_to = models.CharField(max_length=120, blank=True)
    vehicle_number = models.CharField(max_length=40, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    @transaction.atomic
    def confirm_delivery(self, user=None):
        """
        Release the goods and write the outward movements.

        The row is locked first so that a double-click, or two people pressing
        the button at once, cannot get past the status check together.
        """
        locked = DeliveryNote.objects.select_for_update().get(pk=self.pk)
        if locked.status == DeliveryStatus.DELIVERED:
            raise ValueError(f"{self.reference} has already been delivered.")
        self.status = locked.status

        for line in self.lines.select_related("item"):
            if not line.item.tracks_stock:
                continue  # services carry no stock
            record_movement(
                item=line.item,
                movement_type=MovementType.SALE_OUT,
                quantity=line.quantity,
                movement_date=self.document_date,
                source_document="DN",
                source_reference=self.reference,
                user=user,
            )

        self.status = DeliveryStatus.DELIVERED
        self.delivered_at = timezone.now()
        self.save(update_fields=["status", "delivered_at"])
        return self


class DeliveryNoteLine(SalesLine):
    delivery_note = models.ForeignKey(
        DeliveryNote, on_delete=models.CASCADE, related_name="lines"
    )
