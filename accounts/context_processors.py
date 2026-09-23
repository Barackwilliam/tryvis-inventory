"""
What every page of the shell needs: the person's role, which nav item to
light up, the page title, and the small badge counts in the sidebar.
"""
from accounts.models import user_is_manager

# url name -> (sidebar key, page title)
NAV = {
    "dashboard": ("dashboard", "Dashboard"),
    "item_list": ("items", "All items"),
    "item_detail": ("items", "Item"),
    "item_create": ("items", "Add item"),
    "item_edit": ("items", "Edit item"),
    "report_low_stock": ("low", "Running out"),
    "stock_adjust": ("adjust", "Fix stock count"),
    "movement_list": ("history", "Stock history"),
    "purchase_list": ("purchases", "Stock received"),
    "purchase_create": ("purchases", "Record stock received"),
    "purchase_detail": ("purchases", "Stock received"),
    "quotation_list": ("quotations", "Quotations"),
    "quotation_create": ("quotations", "New quotation"),
    "quotation_detail": ("quotations", "Quotation"),
    "invoice_list": ("invoices", "Invoices"),
    "invoice_create": ("invoices", "New invoice"),
    "invoice_detail": ("invoices", "Invoice"),
    "delivery_list": ("deliveries", "Delivery notes"),
    "delivery_create": ("deliveries", "New delivery note"),
    "delivery_detail": ("deliveries", "Delivery note"),
    "customer_list": ("customers", "Customers"),
    "job_list": ("jobs", "Workshop jobs"),
    "job_create": ("jobs", "New workshop job"),
    "job_detail": ("jobs", "Workshop job"),
    "report_movement": ("r-movement", "What sells, what sits"),
    "report_valuation": ("r-value", "Value of stock"),
    "report_profit": ("r-profit", "Profit"),
    "briefing": ("briefing", "The briefing"),
    "user_list": ("users", "People"),
    "user_create": ("users", "Add a person"),
    "user_edit": ("users", "Edit person"),
    "category_list": ("categories", "Groups"),
    "supplier_list": ("suppliers", "Suppliers"),
    "unit_list": ("units", "Units"),
}


def _badge_counts():
    """Three cheap counts for the sidebar. Kept small on purpose."""
    from catalog.models import Item, ItemType
    from jobs.models import JobCard, JobStatus
    from sales.models import Invoice, InvoiceStatus, Quotation, QuotationStatus
    from django.db.models import F

    return {
        "low": Item.objects.filter(
            is_active=True,
            item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE],
            minimum_level__gt=0,
            quantity_on_hand__lte=F("minimum_level"),
        ).count(),
        "quotations": Quotation.objects.filter(
            status__in=[QuotationStatus.DRAFT, QuotationStatus.SENT]
        ).count(),
        "invoices": Invoice.objects.filter(
            status__in=[InvoiceStatus.ISSUED, InvoiceStatus.PART_PAID]
        ).count(),
        "jobs": JobCard.objects.filter(
            status__in=[JobStatus.OPEN, JobStatus.IN_PROGRESS]
        ).count(),
    }


def inventory_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"is_manager": False}

    match = getattr(request, "resolver_match", None)
    key, title = NAV.get(getattr(match, "url_name", ""), ("", ""))

    context = {
        "is_manager": user_is_manager(user),
        "nav_key": key,
        "nav_title": title,
    }
    try:
        context["nav_counts"] = _badge_counts()
    except Exception:
        # Before the first migrate the tables are not there yet; the shell
        # should still render rather than throw a 500 at the person.
        context["nav_counts"] = {}
    return context
