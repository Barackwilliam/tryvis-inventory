import logging
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from inventory import briefing as briefing_engine
from inventory import charts
from inventory import dashboard as dashboard_data

from accounts.models import user_is_manager
from accounts.permissions import inventory_required, manager_required
from catalog.models import Item, ItemType
from inventory.forms import StockAdjustmentForm
from inventory.models import MovementType, StockMovement, record_movement
from inventory.reports import dead_stock_value, movement_analysis
from jobs.models import JobCard
from sales.models import Customer, Invoice, InvoiceStatus, Quotation

logger = logging.getLogger(__name__)


@inventory_required
def dashboard(request):
    """
    The command centre. Every number comes from `inventory.dashboard`, which
    derives it from real records; anything that cannot be derived honestly is
    not shown at all.
    """
    hour = timezone.localtime().hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    data = dashboard_data.build(request.user)

    brief_text = brief_source = brief_at = None
    if user_is_manager(request.user):
        try:
            brief_text, brief_source, brief_at = briefing_engine.get_briefing(data)
        except Exception:
            # A briefing is a nice-to-have. It must never take the dashboard down.
            logger.exception("could not produce the briefing")

    return render(request, "inventory/dashboard.html", {
        "d": data,
        "greeting": greeting,
        "item_create_url": reverse("inventory:item_create"),
        "brief_text": brief_text,
        "brief_paragraphs": brief_text.split("\n\n") if brief_text else [],
        "brief_source": brief_source,
        "brief_at": brief_at,
    })


@manager_required
def briefing_refresh(request):
    """Write a fresh briefing now, ignoring the cache."""
    data = dashboard_data.build(request.user)
    try:
        _, source, _ = briefing_engine.get_briefing(data, force=True)
        messages.success(
            request,
            "New briefing written by Grok." if source == "grok"
            else "New briefing written. Grok was not reachable, so the system wrote it.",
        )
    except Exception:
        logger.exception("briefing refresh failed")
        messages.error(request, "Could not write a new briefing just now.")
    return redirect("inventory:dashboard")


@manager_required
def briefing_detail(request):
    """The full briefing, with every figure it was written from shown beside it."""
    from inventory.models import Briefing

    data = dashboard_data.build(request.user)
    text, source, written_at = briefing_engine.get_briefing(data)
    record = Briefing.objects.filter(text=text).first()

    rows = []
    for key, value in (record.facts if record else {}).items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            value = ", ".join(
                entry.get("name", str(entry)) if isinstance(entry, dict) else str(entry)
                for entry in value
            )
        rows.append({"label": key.replace("_", " ").capitalize(), "value": value})

    return render(request, "inventory/briefing.html", {
        "paragraphs": text.split("\n\n"),
        "source": source,
        "written_at": written_at,
        "fact_rows": rows,
        "history": Briefing.objects.all()[:8],
    })


@inventory_required
def global_search(request):
    """
    One search box over the things people actually look for. Returns JSON for
    the shell's search panel; falls back to a plain page for anyone without
    JavaScript.
    """
    term = request.GET.get("q", "").strip()
    groups = []

    if len(term) >= 2:
        items = Item.objects.filter(
            Q(code__icontains=term) | Q(name__icontains=term)
            | Q(part_number__icontains=term) | Q(barcode__icontains=term)
        ).select_related("unit")[:6]
        groups.append({"label": "Items", "items": [
            {
                "title": f"{item.code} · {item.name}",
                "meta": f"{item.quantity_on_hand:g} {item.unit} in stock",
                "url": reverse("inventory:item_detail", args=[item.pk]),
            }
            for item in items
        ]})

        customers = Customer.objects.filter(
            Q(name__icontains=term) | Q(phone__icontains=term) | Q(tin__icontains=term)
        )[:4]
        groups.append({"label": "Customers", "items": [
            {"title": c.name, "meta": c.phone or "", "url": reverse("inventory:customer_list")}
            for c in customers
        ]})

        invoices = Invoice.objects.filter(
            Q(reference__icontains=term) | Q(customer__name__icontains=term)
        ).select_related("customer")[:4]
        groups.append({"label": "Invoices", "items": [
            {"title": i.reference, "meta": i.customer.name,
             "url": reverse("inventory:invoice_detail", args=[i.pk])}
            for i in invoices
        ]})

        quotations = Quotation.objects.filter(
            Q(reference__icontains=term) | Q(customer__name__icontains=term)
        ).select_related("customer")[:4]
        groups.append({"label": "Quotations", "items": [
            {"title": q.reference, "meta": q.customer.name,
             "url": reverse("inventory:quotation_detail", args=[q.pk])}
            for q in quotations
        ]})

        jobs = JobCard.objects.filter(
            Q(reference__icontains=term) | Q(title__icontains=term)
            | Q(customer__name__icontains=term)
        ).select_related("customer")[:4]
        groups.append({"label": "Workshop jobs", "items": [
            {"title": f"{j.reference} · {j.title}", "meta": j.customer.name,
             "url": reverse("inventory:job_detail", args=[j.pk])}
            for j in jobs
        ]})

    groups = [g for g in groups if g["items"]]

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"query": term, "groups": groups})
    return render(request, "inventory/search.html", {"term": term, "groups": groups})


@inventory_required
def movement_list(request):
    movements = StockMovement.objects.select_related("item", "created_by")

    movement_type = request.GET.get("type")
    if movement_type:
        movements = movements.filter(movement_type=movement_type)

    search = request.GET.get("q", "").strip()
    if search:
        movements = movements.filter(
            Q(item__code__icontains=search)
            | Q(item__name__icontains=search)
            | Q(item__part_number__icontains=search)
            | Q(source_reference__icontains=search)
        ).distinct()

    return render(request, "inventory/movement_list.html", {
        "movements": movements[:300],
        "movement_types": MovementType.choices,
        "selected_type": movement_type,
        "search": search,
    })


@inventory_required
def stock_adjust(request):
    initial = {"movement_date": timezone.now().date()}
    form = StockAdjustmentForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            movement = record_movement(
                item=data["item"],
                movement_type=data["movement_type"],
                quantity=data["quantity"],
                unit_cost=data.get("unit_cost") or None,
                movement_date=data["movement_date"],
                source_document="ADJ",
                notes=data.get("notes", ""),
                user=request.user,
            )
            # read the balance off the movement, not off the form's stale copy
            messages.success(
                request,
                f"Done. {movement.item.code} now shows "
                f"{movement.balance_after:g} {movement.item.unit} in the store.",
            )
            return redirect("inventory:stock_adjust")
        except ValueError as exc:
            messages.error(request, str(exc))
    return render(request, "inventory/stock_adjust.html", {"form": form})


# --- reports -------------------------------------------------------------
@manager_required
def report_movement_analysis(request):
    days = int(request.GET.get("days", 90))
    rows = movement_analysis(days=days)
    classification = request.GET.get("class")
    if classification:
        rows = [row for row in rows if row.classification == classification]
    counts = {"FAST": 0, "NORMAL": 0, "SLOW": 0, "DEAD": 0}
    for row in movement_analysis(days=days):
        counts[row.classification] += 1

    return render(request, "inventory/report_movement.html", {
        "rows": rows,
        "days": days,
        "classification": classification,
        "dead_value": dead_stock_value(days),
        "counts": counts,
        "mix": charts.donut([
            {"label": "Sells fast", "value": counts["FAST"], "colour": charts.GREEN},
            {"label": "Normal", "value": counts["NORMAL"], "colour": charts.BLUE},
            {"label": "Sells slowly", "value": counts["SLOW"], "colour": charts.AMBER},
            {"label": "Not selling", "value": counts["DEAD"], "colour": charts.RED},
        ]),
        "best": charts.horizontal_bars(
            [{"label": r.item.name, "value": float(r.quantity_sold)} for r in rows],
            limit=6, tone=charts.BLUE,
        ),
    })


@manager_required
def report_stock_valuation(request):
    items = Item.objects.filter(
        is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
    ).select_related("category", "unit").order_by("category__name", "name")
    items = list(items)
    total = sum((item.stock_value for item in items), Decimal("0"))

    by_category = {}
    for item in items:
        by_category.setdefault(item.category.name, Decimal("0"))
        by_category[item.category.name] += item.stock_value

    ranked = sorted(by_category.items(), key=lambda kv: kv[1], reverse=True)
    return render(request, "inventory/report_valuation.html", {
        "items": items,
        "total": total,
        "mix": charts.donut([
            {"label": name, "value": float(value), "colour": charts.PALETTE[i % len(charts.PALETTE)]}
            for i, (name, value) in enumerate(ranked[:8])
        ]),
        "top_items": charts.horizontal_bars(
            [{"label": i.name, "value": float(i.stock_value)} for i in items],
            limit=6, tone=charts.BLUE,
        ),
        "category_count": len(by_category),
    })


@inventory_required
def report_low_stock(request):
    items = [
        item
        for item in Item.objects.filter(
            is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
        ).select_related("category", "unit")
        if item.is_below_minimum
    ]
    shortfalls = charts.horizontal_bars(
        [
            {"label": i.name, "value": float(i.minimum_level - i.quantity_on_hand)}
            for i in items
        ],
        limit=8, tone=charts.RED,
    )
    return render(request, "inventory/report_low_stock.html", {
        "items": items,
        "shortfalls": shortfalls,
        "out": sum(1 for i in items if i.quantity_on_hand <= 0),
        "value_to_order": sum(
            ((i.reorder_quantity or (i.minimum_level - i.quantity_on_hand)) * i.average_cost
             for i in items), Decimal("0"),
        ),
    })


@manager_required
def report_profit(request):
    """Gross profit by invoice over a window."""
    days = int(request.GET.get("days", 30))
    start = timezone.now().date() - timedelta(days=days)
    invoices = (
        Invoice.objects.filter(document_date__gte=start)
        .exclude(status=InvoiceStatus.CANCELLED)
        .select_related("customer")
        .prefetch_related("lines__item")
    )
    rows = [
        {
            "invoice": invoice,
            "sales": invoice.subtotal,
            "cost": invoice.cost_of_sale,
            "profit": invoice.gross_profit,
        }
        for invoice in invoices
    ]
    total_sales = sum((r["sales"] for r in rows), Decimal("0"))
    total_cost = sum((r["cost"] for r in rows), Decimal("0"))
    total_profit = total_sales - total_cost

    by_day = {}
    for row in rows:
        key = row["invoice"].document_date
        by_day[key] = by_day.get(key, Decimal("0")) + row["profit"]

    return render(request, "inventory/report_profit.html", {
        "rows": rows,
        "days": days,
        "total_sales": total_sales,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "margin": round(float(total_profit) / float(total_sales) * 100, 1) if total_sales else 0,
        "profit_chart": charts.signed_bars([
            {"label": day.strftime("%d %b"), "value": float(value)}
            for day, value in sorted(by_day.items())[-12:]
        ]),
        "best_invoices": charts.horizontal_bars(
            [{"label": r["invoice"].customer.name, "value": float(r["profit"])} for r in rows],
            limit=6, tone=charts.GREEN,
        ),
    })
