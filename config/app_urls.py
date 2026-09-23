"""
Mount inside the existing Tryvis site project:

    path("inventory/", include("urls")),
"""
from django.urls import path

from accounts import views as account_views
from catalog import views as catalog_views
from inventory import views as inventory_views
from jobs import views as job_views
from purchasing import views as purchasing_views
from sales import views as sales_views

app_name = "inventory"

urlpatterns = [
    path("", inventory_views.dashboard, name="dashboard"),
    path("search/", inventory_views.global_search, name="search"),
    path("briefing/", inventory_views.briefing_detail, name="briefing"),
    path("briefing/refresh/", inventory_views.briefing_refresh, name="briefing_refresh"),

    # catalog
    path("items/", catalog_views.item_list, name="item_list"),
    path("items/new/", catalog_views.item_create, name="item_create"),
    path("items/<int:pk>/", catalog_views.item_detail, name="item_detail"),
    path("items/<int:pk>/edit/", catalog_views.item_edit, name="item_edit"),
    path("categories/", catalog_views.category_list, name="category_list"),
    path("suppliers/", catalog_views.supplier_list, name="supplier_list"),
    path("units/", catalog_views.unit_list, name="unit_list"),

    # stock
    path("movements/", inventory_views.movement_list, name="movement_list"),
    path("stock/adjust/", inventory_views.stock_adjust, name="stock_adjust"),

    # purchasing
    path("purchases/", purchasing_views.purchase_list, name="purchase_list"),
    path("purchases/new/", purchasing_views.purchase_create, name="purchase_create"),
    path("purchases/<int:pk>/", purchasing_views.purchase_detail, name="purchase_detail"),
    path("purchases/<int:pk>/receive/", purchasing_views.purchase_receive, name="purchase_receive"),

    # sales
    path("customers/", sales_views.customer_list, name="customer_list"),
    path("quotations/", sales_views.quotation_list, name="quotation_list"),
    path("quotations/new/", sales_views.quotation_create, name="quotation_create"),
    path("quotations/<int:pk>/", sales_views.quotation_detail, name="quotation_detail"),
    path("quotations/<int:pk>/convert/", sales_views.quotation_convert, name="quotation_convert"),
    path("quotations/<int:pk>/status/<str:status>/", sales_views.quotation_set_status, name="quotation_status"),

    path("invoices/", sales_views.invoice_list, name="invoice_list"),
    path("invoices/new/", sales_views.invoice_create, name="invoice_create"),
    path("invoices/<int:pk>/", sales_views.invoice_detail, name="invoice_detail"),
    path("invoices/<int:pk>/issue/", sales_views.invoice_issue, name="invoice_issue"),
    path("invoices/<int:pk>/deliver/", sales_views.invoice_to_delivery, name="invoice_to_delivery"),
    path("invoices/<int:pk>/efd/", sales_views.invoice_efd_save, name="invoice_efd_save"),
    path("invoices/<int:pk>/efd/clear/", sales_views.invoice_efd_clear, name="invoice_efd_clear"),

    path("delivery-notes/", sales_views.delivery_list, name="delivery_list"),
    path("delivery-notes/new/", sales_views.delivery_create, name="delivery_create"),
    path("delivery-notes/<int:pk>/", sales_views.delivery_detail, name="delivery_detail"),
    path("delivery-notes/<int:pk>/confirm/", sales_views.delivery_confirm, name="delivery_confirm"),

    path("print/<str:doc_type>/<int:pk>/", sales_views.document_print, name="document_print"),

    # jobs
    path("jobs/", job_views.job_list, name="job_list"),
    path("jobs/new/", job_views.job_create, name="job_create"),
    path("jobs/<int:pk>/", job_views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/issue/", job_views.job_issue_materials, name="job_issue"),

    # people
    path("people/", account_views.user_list, name="user_list"),
    path("people/new/", account_views.user_create, name="user_create"),
    path("people/<int:pk>/", account_views.user_edit, name="user_edit"),
    path("people/<int:pk>/password/", account_views.user_set_password, name="user_password"),

    # reports
    path("reports/movement/", inventory_views.report_movement_analysis, name="report_movement"),
    path("reports/valuation/", inventory_views.report_stock_valuation, name="report_valuation"),
    path("reports/low-stock/", inventory_views.report_low_stock, name="report_low_stock"),
    path("reports/profit/", inventory_views.report_profit, name="report_profit"),
]
