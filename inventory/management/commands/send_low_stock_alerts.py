"""
Daily low-stock email.

Run once every morning from a Render Cron Job:

    python manage.py send_low_stock_alerts

It emails every user with `receives_stock_alerts = True` (the Manager, and
whoever else the Manager adds). An item is only reported once - it will not
appear again until stock has been topped up above the minimum and has fallen
back down, which keeps the mail worth opening.
"""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.core.management.base import BaseCommand
from django.db.models import F
from django.template.loader import render_to_string
from django.utils import timezone

from accounts.models import User
from catalog.models import Item, ItemType
from inventory.models import StockAlertLog


class Command(BaseCommand):
    help = "Email the manager about items at or below their minimum level."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Report every low item, even ones already alerted.",
        )

    def handle(self, *args, **options):
        # Clear old alerts for items that have been restocked.
        restocked = StockAlertLog.objects.filter(
            cleared_at__isnull=True,
            item__quantity_on_hand__gt=F("item__minimum_level"),
        )
        cleared = restocked.update(cleared_at=timezone.now())

        low_items = (
            Item.objects.filter(
                is_active=True,
                item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE],
                quantity_on_hand__lte=F("minimum_level"),
                minimum_level__gt=0,
            )
            .select_related("category", "unit")
            .order_by("category__name", "name")
        )

        if not options["force"]:
            already_open = StockAlertLog.objects.filter(
                cleared_at__isnull=True
            ).values_list("item_id", flat=True)
            low_items = low_items.exclude(id__in=list(already_open))

        low_items = list(low_items)
        if not low_items:
            self.stdout.write(
                self.style.SUCCESS(f"Nothing to report. Cleared {cleared} old alerts.")
            )
            return

        recipients = list(
            User.objects.filter(receives_stock_alerts=True, is_active=True)
            .exclude(email="")
            .values_list("email", flat=True)
        )
        if not recipients:
            self.stdout.write(
                self.style.WARNING("No recipients configured - nothing sent.")
            )
            return

        context = {
            "items": low_items,
            "generated_at": timezone.localtime(),
            "company_name": getattr(settings, "COMPANY_NAME", "Tryvis Investments Ltd"),
        }
        subject = f"Low stock alert - {len(low_items)} item(s) need reordering"
        text_body = render_to_string("inventory/email/low_stock.txt", context)
        html_body = render_to_string("inventory/email/low_stock.html", context)

        message = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipients,
        )
        message.attach_alternative(html_body, "text/html")
        message.send()

        StockAlertLog.objects.bulk_create(
            [
                StockAlertLog(
                    item=item,
                    quantity_at_alert=item.quantity_on_hand,
                    minimum_at_alert=item.minimum_level,
                )
                for item in low_items
            ]
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Alerted {len(recipients)} recipient(s) about {len(low_items)} item(s)."
            )
        )
