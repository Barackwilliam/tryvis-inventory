"""
Movement analysis: which items earn their shelf space and which do not.

The classification is turnover based, not just "how many were sold", because
a slow item that ties up a lot of money matters more than a slow cheap one.

    turnover = quantity sold in the window / average quantity held

    FAST    - turnover >= 2.0 over the window
    NORMAL  - turnover between 0.5 and 2.0
    SLOW    - turnover below 0.5 but something moved
    DEAD    - nothing moved at all in the window, yet stock is held
"""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db.models import Max
from django.utils import timezone

from catalog.models import Item, ItemType
from inventory.models import MovementType, StockMovement

FAST_THRESHOLD = Decimal("2.0")
SLOW_THRESHOLD = Decimal("0.5")


LABELS = {
    "FAST": "Sells fast",
    "NORMAL": "Normal",
    "SLOW": "Sells slowly",
    "DEAD": "Not selling",
}


@dataclass
class MovementRow:
    item: Item
    quantity_sold: Decimal
    turnover: Decimal
    classification: str
    days_since_last_sale: int | None
    stock_value: Decimal

    @property
    def label(self):
        return LABELS.get(self.classification, self.classification)


def classify(turnover, quantity_sold):
    if quantity_sold <= 0:
        return "DEAD"
    if turnover >= FAST_THRESHOLD:
        return "FAST"
    if turnover >= SLOW_THRESHOLD:
        return "NORMAL"
    return "SLOW"


def movement_analysis(days=90, category=None):
    """Return one MovementRow per stocked item, best movers first."""
    end = timezone.now().date()
    start = end - timedelta(days=days)

    items = Item.objects.filter(
        is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
    ).select_related("category", "unit")
    if category:
        items = items.filter(category=category)

    sold = {
        row["item"]: row["quantity_sold"]
        for row in StockMovement.objects.sold_between(start, end)
    }

    last_sale = {
        row["item"]: row["last_date"]
        for row in StockMovement.objects.filter(
            movement_type=MovementType.SALE_OUT
        )
        .values("item")
        .annotate(last_date=Max("movement_date"))
    }

    rows = []
    for item in items:
        quantity_sold = Decimal(sold.get(item.id, 0))
        # Average holding: today's stock plus what went out, halved.
        average_held = (item.quantity_on_hand + quantity_sold) / 2
        turnover = (
            quantity_sold / average_held if average_held > 0 else Decimal("0")
        )
        last = last_sale.get(item.id)
        rows.append(
            MovementRow(
                item=item,
                quantity_sold=quantity_sold,
                turnover=turnover.quantize(Decimal("0.01")),
                classification=classify(turnover, quantity_sold),
                days_since_last_sale=(end - last).days if last else None,
                stock_value=item.stock_value,
            )
        )

    rows.sort(key=lambda r: r.turnover, reverse=True)
    return rows


def dead_stock_value(days=90):
    """Total money sitting in items that have not moved at all."""
    return sum(
        (row.stock_value for row in movement_analysis(days) if row.classification == "DEAD"),
        Decimal("0"),
    )
