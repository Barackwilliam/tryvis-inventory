"""
Everything the dashboard shows, worked out from data the system really holds.

Nothing here is invented. Where a number cannot be derived honestly it is not
displayed at all — the screen shows an empty state instead of a guess.

Two things are worth knowing about the history figures:

* Past stock levels are rebuilt by replaying the movement ledger backwards
  from today. That is exact, because the ledger is append-only.
* Past stock *value* uses today's average cost, because the system keeps one
  running average per item rather than a snapshot per day. The shape of the
  line is right; a historical valuation to the shilling would need a daily
  snapshot table. Labelled on screen as "at today's cost" so nobody is misled.
"""
from collections import OrderedDict
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from django.utils import timezone

from catalog.models import Item, ItemType
from inventory.models import INWARD_TYPES, MovementType, StockMovement
from jobs.models import JobCard, JobStatus
from sales.models import (
    DeliveryNote, DeliveryStatus, Invoice, InvoiceStatus, Payment,
    Quotation, QuotationStatus,
)

ZERO = Decimal("0")

# Health bands. The system stores one threshold per item (minimum_level), so
# "critical" is defined here as halfway to empty rather than pretended to be
# a separate field the storekeeper has to maintain.
CRITICAL_FRACTION = Decimal("0.5")


# ---------------------------------------------------------------- helpers
def _month_starts(count=6, today=None):
    today = today or timezone.now().date()
    cursor = today.replace(day=1)
    months = []
    for _ in range(count):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(months))


def _percent_change(current, previous):
    if not previous:
        return None
    return float((Decimal(current) - Decimal(previous)) / Decimal(previous) * 100)


def stocked_items():
    return Item.objects.filter(
        is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
    )


# ---------------------------------------------------------------- health
@dataclass
class HealthBand:
    key: str
    label: str
    count: int
    tone: str

    @property
    def is_empty(self):
        return self.count == 0


def inventory_health(items=None):
    items = list(items if items is not None else stocked_items().select_related("unit"))
    healthy = low = critical = out = 0

    for item in items:
        quantity = item.quantity_on_hand
        minimum = item.minimum_level
        if quantity <= 0:
            out += 1
        elif minimum and quantity <= minimum * CRITICAL_FRACTION:
            critical += 1
        elif minimum and quantity <= minimum:
            low += 1
        else:
            healthy += 1

    total = len(items)
    score = int(round(healthy / total * 100)) if total else 0

    # Ring geometry, worked out here so the template stays free of arithmetic.
    radius = 58
    circumference = 2 * 3.14159265 * radius

    if score >= 85:
        verdict, tone = "Healthy", "success"
    elif score >= 60:
        verdict, tone = "Needs attention", "warning"
    else:
        verdict, tone = "Needs action now", "danger"

    bands = [
        HealthBand("healthy", "Fine", healthy, "success"),
        HealthBand("low", "Getting low", low, "warning"),
        HealthBand("critical", "Almost finished", critical, "danger"),
        HealthBand("out", "Finished", out, "dark"),
    ]
    colours = {"success": "#16A34A", "warning": "#F59E0B", "danger": "#DC2626", "dark": "#94A3B8"}

    return {
        "total": total,
        "score": score,
        "verdict": verdict,
        "tone": tone,
        "bands": bands,
        "segments": [
            {"label": b.label, "count": b.count, "colour": colours[b.tone],
             "percent": round(b.count / total * 100, 1) if total else 0}
            for b in bands if b.count
        ],
        "ring": {
            "radius": radius,
            "circumference": round(circumference, 1),
            "offset": round(circumference * (1 - score / 100), 1),
            "colour": colours[tone],
        },
    }


def stock_alerts(limit=6):
    """Items needing an order, worst first, each with what to do about it."""
    rows = []
    for item in stocked_items().select_related("unit", "category"):
        if not item.minimum_level or item.quantity_on_hand > item.minimum_level:
            continue
        if item.quantity_on_hand <= 0:
            severity, label, tone = 0, "Finished", "danger"
        elif item.quantity_on_hand <= item.minimum_level * CRITICAL_FRACTION:
            severity, label, tone = 1, "Almost finished", "danger"
        else:
            severity, label, tone = 2, "Getting low", "warning"
        shortfall = item.minimum_level - item.quantity_on_hand
        rows.append({
            "item": item,
            "severity": severity,
            "label": label,
            "tone": tone,
            "shortfall": shortfall,
            "suggested": item.reorder_quantity or shortfall,
        })

    rows.sort(key=lambda r: (r["severity"], -float(r["shortfall"])))
    return {
        "rows": rows[:limit],
        "total": len(rows),
        "critical": sum(1 for r in rows if r["severity"] <= 1),
    }


# ---------------------------------------------------------------- value
def stock_value_now(items=None):
    if items is not None:
        return sum((i.quantity_on_hand * i.average_cost for i in items), ZERO)
    return stocked_items().aggregate(
        total=Sum(ExpressionWrapper(
            F("quantity_on_hand") * F("average_cost"),
            output_field=DecimalField(max_digits=20, decimal_places=2),
        ))
    )["total"] or ZERO


def stock_value_history(months=6):
    """
    Replay the ledger backwards to get the value held at each month end.

    Returns oldest first. Empty list when there is nothing to plot, so the
    template can show an empty state rather than a flat fake line.
    """
    items = list(stocked_items())
    if not items:
        return []

    costs = {i.id: i.average_cost for i in items}
    quantities = {i.id: i.quantity_on_hand for i in items}
    today = timezone.now().date()
    starts = _month_starts(months, today)

    # Net movement per item since each cut-off, newest cut-off first.
    points = []
    for start in reversed(starts):
        cut_off = start + timedelta(days=32)
        cut_off = min(cut_off.replace(day=1) - timedelta(days=1), today)
        moved = (
            StockMovement.objects.filter(movement_date__gt=cut_off)
            .values("item", "movement_type")
            .annotate(quantity=Sum("quantity"))
        )
        adjusted = dict(quantities)
        for row in moved:
            if row["item"] not in adjusted:
                continue
            delta = row["quantity"]
            if row["movement_type"] in INWARD_TYPES:
                adjusted[row["item"]] -= delta
            else:
                adjusted[row["item"]] += delta

        value = sum(
            (max(quantity, ZERO) * costs.get(item_id, ZERO)
             for item_id, quantity in adjusted.items()),
            ZERO,
        )
        points.append({"label": start.strftime("%b"), "date": start, "value": value})

    points.reverse()
    if all(p["value"] == ZERO for p in points):
        return []
    return points


def movement_history(months=6):
    """Received vs sold per month — straight out of the ledger."""
    starts = _month_starts(months)
    if not starts:
        return []

    first = starts[0]
    rows = (
        StockMovement.objects.filter(movement_date__gte=first)
        .values("movement_date__year", "movement_date__month", "movement_type")
        .annotate(quantity=Sum("quantity"))
    )

    buckets = OrderedDict(
        (start, {"label": start.strftime("%b"), "received": ZERO, "sold": ZERO,
                 "adjusted": ZERO, "returned": ZERO})
        for start in starts
    )
    for row in rows:
        key = date(row["movement_date__year"], row["movement_date__month"], 1)
        bucket = buckets.get(key)
        if not bucket:
            continue
        kind = row["movement_type"]
        if kind in (MovementType.PURCHASE_IN, MovementType.OPENING):
            bucket["received"] += row["quantity"]
        elif kind == MovementType.SALE_OUT:
            bucket["sold"] += row["quantity"]
        elif kind in (MovementType.RETURN_IN, MovementType.RETURN_OUT):
            bucket["returned"] += row["quantity"]
        else:
            bucket["adjusted"] += row["quantity"]

    values = list(buckets.values())
    if all(v["received"] == ZERO and v["sold"] == ZERO for v in values):
        return []
    return values


# ---------------------------------------------------------------- charts
def line_chart_svg(points, width=640, height=180, tone="#2563EB"):
    """A small inline SVG line chart. No chart library, no extra request."""
    if len(points) < 2:
        return None

    values = [float(p["value"]) for p in points]
    low, high = min(values), max(values)
    if high == low:
        high = low + 1
    pad_x, pad_y = 8, 14
    span_x = width - pad_x * 2
    span_y = height - pad_y * 2

    coords = []
    for index, value in enumerate(values):
        x = pad_x + span_x * index / (len(values) - 1)
        y = pad_y + span_y * (1 - (value - low) / (high - low))
        coords.append((round(x, 1), round(y, 1)))

    line = " ".join(f"{'M' if i == 0 else 'L'}{x},{y}" for i, (x, y) in enumerate(coords))
    area = line + f" L{coords[-1][0]},{height} L{coords[0][0]},{height} Z"
    dots = "".join(
        f'<circle cx="{x}" cy="{y}" r="3" fill="{tone}" />' for x, y in coords[-1:]
    )
    return {
        "width": width, "height": height, "line": line, "area": area,
        "dots": dots, "tone": tone,
        "labels": [
            {"x": round(coords[i][0], 1), "text": p["label"]}
            for i, p in enumerate(points)
        ],
    }


def bar_chart_svg(rows, width=640, height=190):
    """Grouped bars: received against sold."""
    if not rows:
        return None

    peak = max(
        [float(r["received"]) for r in rows] + [float(r["sold"]) for r in rows] + [1]
    )
    pad_y = 18
    span_y = height - pad_y - 22
    group_width = width / len(rows)
    bar_width = min(18, group_width / 3.4)
    gap = 5

    bars = []
    for index, row in enumerate(rows):
        centre = group_width * (index + 0.5)
        for offset, key, tone in (
            (-(bar_width + gap) / 2, "received", "#2563EB"),
            ((bar_width + gap) / 2, "sold", "#38BDF8"),
        ):
            value = float(row[key])
            bar_height = max(2, span_y * value / peak) if value else 2
            bars.append({
                "x": round(centre + offset - bar_width / 2, 1),
                "y": round(pad_y + span_y - bar_height, 1),
                "w": round(bar_width, 1),
                "h": round(bar_height, 1),
                "tone": tone,
                "faint": value == 0,
                "title": f"{row['label']} {key}: {value:,.0f}",
            })

    return {
        "width": width, "height": height, "bars": bars,
        "baseline": round(pad_y + span_y, 1),
        "labels": [
            {"x": round(group_width * (i + 0.5), 1), "text": r["label"]}
            for i, r in enumerate(rows)
        ],
    }


# ---------------------------------------------------------------- money
def sales_summary():
    today = timezone.now().date()
    month_start = today.replace(day=1)
    previous_start = (month_start - timedelta(days=1)).replace(day=1)

    invoices = list(
        Invoice.objects.exclude(status=InvoiceStatus.CANCELLED)
        .select_related("customer")
        .prefetch_related("lines__item")
    )

    this_month = sum(
        (i.subtotal for i in invoices if i.document_date >= month_start), ZERO
    )
    last_month = sum(
        (i.subtotal for i in invoices
         if previous_start <= i.document_date < month_start), ZERO
    )

    open_invoices = [
        i for i in invoices
        if i.status in (InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID)
    ]
    overdue = [i for i in open_invoices if i.is_overdue]

    collected = Payment.objects.filter(paid_on__gte=month_start).aggregate(
        total=Sum("amount")
    )["total"] or ZERO

    return {
        "this_month": this_month,
        "last_month": last_month,
        "change": _percent_change(this_month, last_month),
        "outstanding": sum((i.balance_due for i in open_invoices), ZERO),
        "unpaid_count": len(open_invoices),
        "overdue_count": len(overdue),
        "overdue_value": sum((i.balance_due for i in overdue), ZERO),
        "collected_this_month": collected,
        "recent_unpaid": sorted(
            open_invoices, key=lambda i: (not i.is_overdue, i.document_date)
        )[:5],
    }


def quotation_summary():
    today = timezone.now().date()
    quotations = list(Quotation.objects.select_related("customer").prefetch_related("lines__item"))

    waiting, expired = [], []
    for quotation in quotations:
        if quotation.status not in (QuotationStatus.DRAFT, QuotationStatus.SENT):
            continue
        if quotation.valid_until and quotation.valid_until < today:
            expired.append(quotation)
        else:
            waiting.append(quotation)

    return {
        "waiting": len(waiting),
        "expired": len(expired),
        "accepted": sum(1 for q in quotations if q.status == QuotationStatus.ACCEPTED),
        "invoiced": sum(1 for q in quotations if q.status == QuotationStatus.INVOICED),
        "waiting_value": sum((q.grand_total for q in waiting), ZERO),
        "recent": sorted(waiting, key=lambda q: q.document_date, reverse=True)[:5],
    }


def workshop_summary():
    today = timezone.now().date()
    month_start = today.replace(day=1)
    jobs = list(JobCard.objects.select_related("customer"))

    active = [j for j in jobs if j.is_open]
    return {
        "active": len(active),
        "due_today": sum(1 for j in active if j.due_date == today),
        "overdue": sum(1 for j in active if j.is_overdue),
        "completed_this_month": sum(
            1 for j in jobs
            if j.completed_date and j.completed_date >= month_start
        ),
        "recent": sorted(active, key=lambda j: (j.due_date or date.max, -j.id))[:5],
    }


def pending_deliveries():
    return list(
        DeliveryNote.objects.filter(status=DeliveryStatus.DRAFT)
        .select_related("customer")[:5]
    )


# ---------------------------------------------------------------- activity
def recent_activity(limit=12):
    movements = (
        StockMovement.objects.select_related("item", "item__unit", "created_by")[:limit]
    )
    rows = []
    for movement in movements:
        if movement.movement_type in (MovementType.PURCHASE_IN, MovementType.OPENING):
            tone, verb = "success", "Stock came in"
        elif movement.movement_type == MovementType.SALE_OUT:
            tone, verb = "primary", "Sold to customer"
        elif movement.movement_type == MovementType.JOB_ISSUE:
            tone, verb = "info", "Used on a job"
        elif movement.movement_type in (MovementType.RETURN_IN, MovementType.RETURN_OUT):
            tone, verb = "info", "Returned"
        else:
            tone, verb = "warning", "Count corrected"
        today = timezone.now().date()
        if movement.movement_date == today:
            when = timezone.localtime(movement.created_at).strftime("%H:%M")
        else:
            when = movement.movement_date.strftime("%d %b")
        rows.append({
            "movement": movement,
            "verb": verb,
            "tone": tone,
            "when": when,
            "sign": "+" if movement.is_inward else "-",
        })
    return rows


# ---------------------------------------------------------------- top level
def build(user):
    """Everything the dashboard template needs, in one pass."""
    items = list(stocked_items().select_related("unit", "category"))
    today = timezone.now().date()
    month_start = today.replace(day=1)
    previous_start = (month_start - timedelta(days=1)).replace(day=1)

    value_points = stock_value_history()
    movement_points = movement_history()

    item_count = len(items)
    items_added = sum(
        1 for i in items if i.created_at and i.created_at.date() >= month_start
    )
    items_before = item_count - items_added

    sold_this_month = StockMovement.objects.filter(
        movement_type=MovementType.SALE_OUT, movement_date__gte=month_start
    ).aggregate(total=Sum("quantity"))["total"] or ZERO
    sold_last_month = StockMovement.objects.filter(
        movement_type=MovementType.SALE_OUT,
        movement_date__gte=previous_start,
        movement_date__lt=month_start,
    ).aggregate(total=Sum("quantity"))["total"] or ZERO

    received_this_month = StockMovement.objects.filter(
        movement_type=MovementType.PURCHASE_IN, movement_date__gte=month_start
    ).aggregate(total=Sum("quantity"))["total"] or ZERO

    value_now = stock_value_now(items)
    value_change = (
        _percent_change(value_now, value_points[-2]["value"])
        if len(value_points) >= 2 else None
    )

    return {
        "today": today,
        "item_count": item_count,
        "items_added": items_added,
        "item_change": _percent_change(item_count, items_before),
        "stock_value": value_now,
        "stock_value_change": value_change,
        "sold_this_month": sold_this_month,
        "sold_change": _percent_change(sold_this_month, sold_last_month),
        "received_this_month": received_this_month,
        "health": inventory_health(items),
        "alerts": stock_alerts(),
        "value_chart": line_chart_svg(value_points),
        "value_points": value_points,
        "movement_chart": bar_chart_svg(movement_points),
        "movement_points": movement_points,
        "sales": sales_summary(),
        "quotations": quotation_summary(),
        "workshop": workshop_summary(),
        "pending_deliveries": pending_deliveries(),
        "activity": recent_activity(),
    }
