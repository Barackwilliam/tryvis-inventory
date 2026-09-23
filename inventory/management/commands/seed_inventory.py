"""
Seed the system with a small, realistic starting set so the client can see it
working before keying in the real stock.

    python manage.py seed_inventory
    python manage.py seed_inventory --reset   (clears seeded data first)
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Role
from catalog.models import Category, Item, ItemType, Supplier, UnitOfMeasure
from inventory.models import MovementType, record_movement
from sales.models import Customer

UNITS = [("Piece", "pcs"), ("Set", "set"), ("Metre", "m"), ("Kilogram", "kg"), ("Litre", "L"), ("Hour", "hr")]

CATEGORIES = [
    ("Bearings", "BRG"),
    ("Cutting & Grinding", "CTD"),
    ("Power Transmission", "PTR"),
    ("Seals & Gaskets", "SEA"),
    ("Welding & Gas", "WLD"),
    ("Services", "SRV"),
]

# name, part no, category code, unit, type, min, reorder, cost, price
ITEMS = [
    ("Ball Bearing 6204 2RS", "6204-2RS", "BRG", "pcs", ItemType.STOCK, 10, 40, 8500, 14000),
    ("Ball Bearing 6205 2RS", "6205-2RS", "BRG", "pcs", ItemType.STOCK, 10, 40, 9800, 16000),
    ("Spherical Roller Bearing 22324", "22324", "BRG", "pcs", ItemType.STOCK, 2, 6, 385000, 560000),
    ("Cutting Disc 14 inch", "CD-355", "CTD", "pcs", ItemType.STOCK, 20, 100, 4200, 7000),
    ("Grinding Disc 7 inch", "GD-180", "CTD", "pcs", ItemType.STOCK, 15, 60, 3600, 6000),
    ("V-Belt B-75", "B75", "PTR", "pcs", ItemType.STOCK, 8, 30, 12500, 20000),
    ("Roller Chain 12B-1", "12B-1", "PTR", "m", ItemType.STOCK, 5, 25, 18000, 29000),
    ("Oil Seal 45x62x8", "TC-456208", "SEA", "pcs", ItemType.STOCK, 12, 50, 3200, 5500),
    ("Welding Rod E6013 3.2mm", "E6013-3.2", "WLD", "kg", ItemType.CONSUMABLE, 20, 80, 5400, 8500),
    ("Machining & Fabrication Labour", "", "SRV", "hr", ItemType.SERVICE, 0, 0, 0, 25000),
]


class Command(BaseCommand):
    help = "Create demo categories, units, items, a supplier, a customer and opening stock."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Delete seeded records first.")

    @transaction.atomic
    def handle(self, *args, **options):
        if options["reset"]:
            Item.objects.all().delete()
            Category.objects.all().delete()
            UnitOfMeasure.objects.all().delete()
            self.stdout.write(self.style.WARNING("Seeded catalog cleared."))

        units = {}
        for name, abbreviation in UNITS:
            unit, _ = UnitOfMeasure.objects.get_or_create(
                abbreviation=abbreviation, defaults={"name": name}
            )
            units[abbreviation] = unit

        categories = {}
        for name, code in CATEGORIES:
            category, _ = Category.objects.get_or_create(code=code, defaults={"name": name})
            categories[code] = category

        supplier, _ = Supplier.objects.get_or_create(
            name="Shanghai Bearing Trading Co.",
            defaults={
                "country": "China", "is_foreign": True,
                "contact_person": "Li Wei", "email": "sales@example.cn",
            },
        )
        Supplier.objects.get_or_create(
            name="Kariakoo Hardware Supplies",
            defaults={"country": "Tanzania", "phone": "+255 712 000 000"},
        )
        Customer.objects.get_or_create(
            name="Azania Cement Works Ltd",
            defaults={"phone": "+255 754 111 222", "address": "Wazo Hill, Dar es Salaam", "tin": "123-456-789"},
        )
        Customer.objects.get_or_create(
            name="Mikocheni Steel Rolling Mills",
            defaults={"phone": "+255 765 333 444", "address": "Mikocheni Industrial Area, Dar es Salaam"},
        )

        created = 0
        for name, part_no, cat_code, unit_abbr, item_type, minimum, reorder, cost, price in ITEMS:
            if Item.objects.filter(name=name).exists():
                continue
            item = Item.objects.create(
                name=name,
                part_number=part_no,
                category=categories[cat_code],
                unit=units[unit_abbr],
                item_type=item_type,
                minimum_level=Decimal(minimum),
                reorder_quantity=Decimal(reorder),
                selling_price=Decimal(price),
                location="Main store",
            )
            created += 1

            if item.tracks_stock:
                # Opening balance: a bit above minimum, and one item deliberately low
                opening = Decimal(minimum) * 3 if name != "Cutting Disc 14 inch" else Decimal(minimum) - 5
                if opening > 0:
                    record_movement(
                        item=item,
                        movement_type=MovementType.OPENING,
                        quantity=opening,
                        unit_cost=Decimal(cost),
                        movement_date=timezone.now().date(),
                        source_document="SEED",
                        notes="Opening balance (demo data)",
                    )

        manager = get_user_model().objects.filter(is_superuser=True).first()
        if manager:
            manager.role = Role.MANAGER
            manager.receives_stock_alerts = True
            manager.save(update_fields=["role", "receives_stock_alerts"])

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {created} item(s), {len(categories)} categories, {len(units)} units, "
            f"2 suppliers and 2 customers. One item is deliberately below its minimum so "
            f"you can see the alert working."
        ))
