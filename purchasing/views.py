from collections import OrderedDict
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.permissions import manager_required
from inventory import charts
from purchasing.forms import PurchaseForm, PurchaseLineFormSet
from purchasing.models import Purchase, PurchaseStatus


@manager_required
def purchase_list(request):
    purchases = list(
        Purchase.objects.select_related("supplier").prefetch_related("lines__item")[:200]
    )

    cursor = timezone.now().date().replace(day=1)
    months = []
    for _ in range(6):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    months.reverse()

    buckets = OrderedDict(
        (m, {"label": m.strftime("%b"), "goods": Decimal("0"), "extras": Decimal("0")})
        for m in months
    )
    spend = extras = Decimal("0")
    drafts = 0
    for purchase in purchases:
        if purchase.status == PurchaseStatus.DRAFT:
            drafts += 1
            continue
        spend += purchase.landed_total
        extras += purchase.additional_charges
        key = purchase.purchase_date.replace(day=1)
        if key in buckets:
            buckets[key]["goods"] += purchase.goods_total_tzs
            buckets[key]["extras"] += purchase.additional_charges

    rows = list(buckets.values())
    return render(request, "inventory/purchase_list.html", {
        "purchases": purchases,
        "summary": {
            "count": len(purchases),
            "drafts": drafts,
            "spend": spend,
            "extras": extras,
            "extras_share": round(float(extras) / float(spend) * 100, 1) if spend else 0,
            "this_month": rows[-1]["goods"] + rows[-1]["extras"] if rows else Decimal("0"),
        },
        "spend_chart": charts.grouped_bars(rows, [
            ("goods", charts.BLUE, "Goods"),
            ("extras", charts.AMBER, "Shipping & customs"),
        ]),
    })


@manager_required
def purchase_create(request):
    form = PurchaseForm(request.POST or None, initial={"purchase_date": timezone.now().date()})
    formset = PurchaseLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        purchase = form.save(commit=False)
        purchase.created_by = request.user
        purchase.save()
        formset.instance = purchase
        formset.save()
        messages.success(
            request,
            f"{purchase.reference} saved. Check the items, then press "
            f"'Add to store' to put them into stock.",
        )
        return redirect("inventory:purchase_detail", pk=purchase.pk)
    return render(request, "inventory/purchase_form.html", {
        "form": form, "formset": formset, "title": "New goods received note",
    })


@manager_required
def purchase_detail(request, pk):
    purchase = get_object_or_404(
        Purchase.objects.select_related("supplier").prefetch_related("lines__item"), pk=pk
    )
    return render(request, "inventory/purchase_detail.html", {"purchase": purchase})


@manager_required
def purchase_receive(request, pk):
    purchase = get_object_or_404(Purchase, pk=pk)
    try:
        purchase.receive(user=request.user)
        messages.success(
            request,
            f"{purchase.reference} added to the store. Shipping and customs have been "
            f"shared across the items, so the cost of each piece is now correct.",
        )
    except (ValueError, Exception) as exc:
        messages.error(request, f"Could not add {purchase.reference} to the store: {exc}")
    return redirect("inventory:purchase_detail", pk=pk)
