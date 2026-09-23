from collections import defaultdict
from decimal import Decimal

from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import inventory_required, manager_required
from catalog.forms import CategoryForm, ItemForm, SupplierForm, UnitForm
from catalog.models import Category, Item, Supplier, UnitOfMeasure
from inventory import charts
from inventory.models import INWARD_TYPES, StockMovement


@inventory_required
def item_list(request):
    items = Item.objects.select_related("category", "unit").all()

    search = request.GET.get("q", "").strip()
    if search:
        items = items.filter(
            Q(code__icontains=search)
            | Q(name__icontains=search)
            | Q(part_number__icontains=search)
            | Q(barcode__icontains=search)
        )

    category_id = request.GET.get("category")
    if category_id:
        items = items.filter(category_id=category_id)

    if request.GET.get("low") == "1":
        items = [i for i in items if i.is_below_minimum]

    items = list(items)

    # a small picture of the catalogue above the list
    by_category = defaultdict(Decimal)
    stock_value = Decimal("0")
    low = out = 0
    for item in items:
        if not item.tracks_stock:
            continue
        stock_value += item.stock_value
        by_category[item.category.name] += item.stock_value
        if item.quantity_on_hand <= 0:
            out += 1
        elif item.is_below_minimum:
            low += 1

    return render(request, "inventory/item_list.html", {
        "items": items,
        "categories": Category.objects.all(),
        "search": search,
        "selected_category": category_id,
        "low_only": request.GET.get("low") == "1",
        "summary": {
            "total": len(items),
            "low": low,
            "out": out,
            "value": stock_value,
        },
        "by_category": charts.horizontal_bars(
            [{"label": name, "value": value} for name, value in by_category.items()]
        ),
    })


@inventory_required
def item_detail(request, pk):
    item = get_object_or_404(Item.objects.select_related("category", "unit"), pk=pk)
    movements = list(
        StockMovement.objects.filter(item=item).select_related("created_by")[:100]
    )

    # how the stock level has moved, oldest first, straight off the ledger
    history = [
        {"label": m.movement_date.strftime("%d %b"), "value": float(m.balance_after)}
        for m in reversed(movements[:24])
    ]
    received = sum(
        (m.quantity for m in movements if m.movement_type in INWARD_TYPES), Decimal("0")
    )
    issued = sum(
        (m.quantity for m in movements if m.movement_type not in INWARD_TYPES), Decimal("0")
    )

    return render(request, "inventory/item_detail.html", {
        "item": item,
        "movements": movements,
        "level_chart": charts.line_chart(history, height=150, fill_id="levelFill"),
        "level_points": history,
        "received": received,
        "issued": issued,
    })


@inventory_required
def item_create(request):
    form = ItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.created_by = request.user
        item.save()
        messages.success(request, f"Saved. This item's code is {item.code}.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/item_form.html", {"form": form, "title": "New item"})


@inventory_required
def item_edit(request, pk):
    item = get_object_or_404(Item, pk=pk)
    form = ItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{item.code} updated.")
        return redirect("inventory:item_detail", pk=item.pk)
    return render(request, "inventory/item_form.html", {
        "form": form, "title": f"Edit {item.code}", "item": item,
    })


# --- simple setup screens, Manager only ---------------------------------
def _simple_list(request, model, form_class, title, template="inventory/setup_list.html"):
    form = form_class(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, f"{title[:-1] if title.endswith('s') else title} saved.")
        return redirect(request.path)
    return render(request, template, {
        "objects": model.objects.all(), "form": form, "title": title,
    })


@manager_required
def category_list(request):
    return _simple_list(request, Category, CategoryForm, "Categories")


@manager_required
def supplier_list(request):
    return _simple_list(request, Supplier, SupplierForm, "Suppliers")


@manager_required
def unit_list(request):
    return _simple_list(request, UnitOfMeasure, UnitForm, "Units of measure")
