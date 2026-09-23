from collections import OrderedDict
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import user_is_manager
from accounts.permissions import inventory_required
from inventory import charts
from core.pdf import render_pdf
from sales.forms import (
    CustomerForm, DeliveryNoteForm, DeliveryNoteLineFormSet, InvoiceForm,
    InvoiceLineFormSet, PaymentForm, QuotationForm, QuotationLineFormSet,
)
from sales.models import (
    Customer, DeliveryNote, DeliveryStatus, Invoice, InvoiceStatus,
    Payment, Quotation, QuotationStatus,
)


# --- customers -----------------------------------------------------------
@inventory_required
def customer_list(request):
    form = CustomerForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        customer = form.save(commit=False)
        customer.created_by = request.user
        customer.save()
        messages.success(request, f"{customer.name} saved.")
        return redirect("inventory:customer_list")
    return render(request, "inventory/customer_list.html", {
        "customers": Customer.objects.all(), "form": form,
    })


# --- quotations ----------------------------------------------------------
def _month_labels(count=6):
    cursor = timezone.now().date().replace(day=1)
    months = []
    for _ in range(count):
        months.append(cursor)
        cursor = (cursor - timedelta(days=1)).replace(day=1)
    return list(reversed(months))


@inventory_required
def quotation_list(request):
    quotations = list(
        Quotation.objects.select_related("customer").prefetch_related("lines__item")[:200]
    )
    today = timezone.now().date()

    waiting = accepted = invoiced = lost = expired = 0
    waiting_value = Decimal("0")
    for quotation in quotations:
        if quotation.status in (QuotationStatus.DRAFT, QuotationStatus.SENT):
            if quotation.valid_until and quotation.valid_until < today:
                expired += 1
            else:
                waiting += 1
                waiting_value += quotation.grand_total
        elif quotation.status == QuotationStatus.ACCEPTED:
            accepted += 1
        elif quotation.status == QuotationStatus.INVOICED:
            invoiced += 1
        else:
            lost += 1

    return render(request, "inventory/quotation_list.html", {
        "quotations": quotations,
        "summary": {
            "waiting": waiting, "accepted": accepted, "invoiced": invoiced,
            "expired": expired, "lost": lost, "waiting_value": waiting_value,
            "win_rate": round(invoiced / len(quotations) * 100) if quotations else 0,
        },
        "mix": charts.donut([
            {"label": "Waiting", "value": waiting, "colour": charts.BLUE},
            {"label": "Accepted", "value": accepted, "colour": charts.GREEN},
            {"label": "Invoiced", "value": invoiced, "colour": charts.SKY},
            {"label": "Expired", "value": expired, "colour": charts.AMBER},
            {"label": "Lost", "value": lost, "colour": charts.SLATE},
        ]),
    })


@inventory_required
def quotation_create(request):
    form = QuotationForm(request.POST or None, initial={"document_date": timezone.now().date()})
    formset = QuotationLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        quotation = form.save(commit=False)
        quotation.created_by = request.user
        quotation.save()
        formset.instance = quotation
        formset.save()
        messages.success(request, f"Quotation {quotation.reference} created.")
        return redirect("inventory:quotation_detail", pk=quotation.pk)
    return render(request, "inventory/document_form.html", {
        "form": form, "formset": formset, "title": "New quotation",
    })


@inventory_required
def quotation_detail(request, pk):
    quotation = get_object_or_404(
        Quotation.objects.select_related("customer").prefetch_related("lines__item"), pk=pk
    )
    return render(request, "inventory/quotation_detail.html", {"quotation": quotation})


@inventory_required
def quotation_convert(request, pk):
    quotation = get_object_or_404(Quotation, pk=pk)
    try:
        invoice = quotation.convert_to_invoice(user=request.user)
        messages.success(request, f"{quotation.reference} is now invoice {invoice.reference}.")
        return redirect("inventory:invoice_detail", pk=invoice.pk)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("inventory:quotation_detail", pk=pk)


@inventory_required
def quotation_set_status(request, pk, status):
    quotation = get_object_or_404(Quotation, pk=pk)
    valid = {choice[0] for choice in QuotationStatus.choices}
    if status.upper() in valid:
        quotation.status = status.upper()
        quotation.save(update_fields=["status"])
        messages.success(request, f"{quotation.reference} marked {quotation.get_status_display()}.")
    return redirect("inventory:quotation_detail", pk=pk)


# --- invoices ------------------------------------------------------------
@inventory_required
def invoice_list(request):
    invoices = list(
        Invoice.objects.select_related("customer").prefetch_related("lines__item")[:200]
    )
    show_money = user_is_manager(request.user)

    outstanding = overdue_value = Decimal("0")
    unpaid = overdue = 0
    for invoice in invoices:
        if invoice.status in (InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID):
            unpaid += 1
            outstanding += invoice.balance_due
            if invoice.is_overdue:
                overdue += 1
                overdue_value += invoice.balance_due

    months = _month_labels()
    buckets = OrderedDict((m, {"label": m.strftime("%b"), "billed": Decimal("0"),
                               "collected": Decimal("0")}) for m in months)
    for invoice in invoices:
        key = invoice.document_date.replace(day=1)
        if key in buckets and invoice.status != InvoiceStatus.CANCELLED:
            buckets[key]["billed"] += invoice.subtotal
    for payment in Payment.objects.filter(paid_on__gte=months[0]):
        key = payment.paid_on.replace(day=1)
        if key in buckets:
            buckets[key]["collected"] += payment.amount

    rows = list(buckets.values())
    collected_this_month = rows[-1]["collected"] if rows else Decimal("0")

    return render(request, "inventory/invoice_list.html", {
        "invoices": invoices,
        "show_money": show_money,
        "summary": {
            "unpaid": unpaid, "overdue": overdue,
            "outstanding": outstanding, "overdue_value": overdue_value,
            "collected_this_month": collected_this_month,
        },
        "money_chart": charts.grouped_bars(rows, [
            ("billed", charts.BLUE, "Billed"),
            ("collected", charts.GREEN, "Collected"),
        ]) if show_money else None,
    })


@inventory_required
def invoice_create(request):
    form = InvoiceForm(request.POST or None, initial={"document_date": timezone.now().date()})
    formset = InvoiceLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        invoice = form.save(commit=False)
        invoice.created_by = request.user
        invoice.save()
        formset.instance = invoice
        formset.save()
        messages.success(request, f"Invoice {invoice.reference} created.")
        return redirect("inventory:invoice_detail", pk=invoice.pk)
    return render(request, "inventory/document_form.html", {
        "form": form, "formset": formset, "title": "New invoice",
    })


@inventory_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(
        Invoice.objects.select_related("customer", "quotation").prefetch_related("lines__item"), pk=pk
    )
    payment_form = PaymentForm(request.POST or None, initial={"paid_on": timezone.now().date()})
    if request.method == "POST" and payment_form.is_valid():
        payment = payment_form.save(commit=False)
        payment.invoice = invoice
        payment.created_by = request.user
        payment.save()          # refreshes the invoice total and status
        invoice.refresh_from_db()
        messages.success(request, f"Payment saved. The customer still owes {invoice.balance_due:,.2f}.")
        return redirect("inventory:invoice_detail", pk=pk)
    return render(request, "inventory/invoice_detail.html", {
        "invoice": invoice, "payment_form": payment_form,
    })


@inventory_required
def invoice_issue(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    invoice.status = InvoiceStatus.ISSUED
    invoice.save(update_fields=["status"])
    messages.success(request, f"{invoice.reference} marked as sent.")
    return redirect("inventory:invoice_detail", pk=pk)


@inventory_required
def invoice_to_delivery(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    note = invoice.create_delivery_note(user=request.user)
    messages.success(request, f"Delivery note {note.reference} made. The goods stay in the store until you confirm it.")
    return redirect("inventory:delivery_detail", pk=note.pk)


# --- delivery notes ------------------------------------------------------
@inventory_required
def delivery_list(request):
    notes = list(DeliveryNote.objects.select_related("customer", "invoice")[:200])
    waiting = sum(1 for n in notes if n.status == DeliveryStatus.DRAFT)
    month_start = timezone.now().date().replace(day=1)
    return render(request, "inventory/delivery_list.html", {
        "notes": notes,
        "summary": {
            "waiting": waiting,
            "delivered": sum(1 for n in notes if n.status == DeliveryStatus.DELIVERED),
            "this_month": sum(
                1 for n in notes
                if n.status == DeliveryStatus.DELIVERED and n.document_date >= month_start
            ),
        },
    })


@inventory_required
def delivery_create(request):
    form = DeliveryNoteForm(request.POST or None, initial={"document_date": timezone.now().date()})
    formset = DeliveryNoteLineFormSet(request.POST or None)
    if request.method == "POST" and form.is_valid() and formset.is_valid():
        note = form.save(commit=False)
        note.created_by = request.user
        note.save()
        formset.instance = note
        formset.save()
        messages.success(request, f"Delivery note {note.reference} created.")
        return redirect("inventory:delivery_detail", pk=note.pk)
    return render(request, "inventory/document_form.html", {
        "form": form, "formset": formset, "title": "New delivery note",
    })


@inventory_required
def delivery_detail(request, pk):
    note = get_object_or_404(
        DeliveryNote.objects.select_related("customer", "invoice").prefetch_related("lines__item"), pk=pk
    )
    return render(request, "inventory/delivery_detail.html", {"note": note})


@inventory_required
def delivery_confirm(request, pk):
    note = get_object_or_404(DeliveryNote, pk=pk)
    try:
        note.confirm_delivery(user=request.user)
        messages.success(request, f"{note.reference} confirmed. The goods have left the store.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("inventory:delivery_detail", pk=pk)


# --- printing ------------------------------------------------------------
PRINTABLE = {
    "quotation": (Quotation, "inventory/print/quotation.html", "Quotation"),
    "invoice": (Invoice, "inventory/print/invoice.html", "Invoice"),
    "delivery": (DeliveryNote, "inventory/print/delivery_note.html", "Delivery Note"),
}


@inventory_required
def document_print(request, doc_type, pk):
    model, template, label = PRINTABLE[doc_type]
    document = get_object_or_404(
        model.objects.select_related("customer").prefetch_related("lines__item"), pk=pk
    )
    context = {
        "doc": document,
        "doc_label": label,
        "doc_type": doc_type,
        "company": {
            "name": settings.COMPANY_NAME,
            "tagline": settings.COMPANY_TAGLINE,
            "address": settings.COMPANY_ADDRESS,
            "website": settings.COMPANY_WEBSITE,
            "phone": settings.COMPANY_PHONE,
            "tin": settings.COMPANY_TIN,
        },
    }
    if request.GET.get("pdf") == "1":
        return render_pdf(template, context, f"{document.reference}.pdf")
    return render(request, template, context)
