"""
Regression tests.

Every test here exists because something was actually wrong. Each one names
the bug it guards, so nobody has to guess later why the assertion matters.

    python manage.py test
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Role
from catalog.models import Category, Item, ItemType, Supplier, UnitOfMeasure
from inventory.models import MovementType, StockMovement, record_movement
from jobs.models import JobCard, JobMaterial
from purchasing.models import AllocationMethod, Purchase, PurchaseLine
from sales.models import (
    Customer, DeliveryStatus, Payment, Quotation, QuotationLine,
)

User = get_user_model()


class Base(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            "manager", "m@tryvis.co.tz", "pw", role=Role.MANAGER
        )
        self.shopkeeper = User.objects.create_user(
            "shop", "s@tryvis.co.tz", "pw", role=Role.SHOPKEEPER
        )
        self.unit = UnitOfMeasure.objects.create(name="Piece", abbreviation="pcs")
        self.category = Category.objects.create(name="Bearings", code="BRG")
        self.customer = Customer.objects.create(name="Azania Cement")
        self.supplier = Supplier.objects.create(name="Shanghai Bearing", is_foreign=True)
        self.item = self.make_item("Ball Bearing 6204", minimum=10)
        record_movement(
            item=self.item, movement_type=MovementType.OPENING,
            quantity=Decimal("100"), unit_cost=Decimal("8000"),
        )
        self.item.refresh_from_db()

    def make_item(self, name, minimum=0, kind=ItemType.STOCK):
        return Item.objects.create(
            name=name, category=self.category, unit=self.unit, item_type=kind,
            minimum_level=Decimal(minimum), selling_price=Decimal("14000"),
        )

    def invoice_for(self, quantity=5):
        quotation = Quotation.objects.create(customer=self.customer)
        QuotationLine.objects.create(
            quotation=quotation, item=self.item,
            quantity=Decimal(quantity), unit_price=Decimal("14000"),
        )
        return quotation.convert_to_invoice(user=self.manager)


class StockLedger(Base):
    def test_stock_cannot_go_negative(self):
        with self.assertRaises(ValueError):
            record_movement(
                item=self.item, movement_type=MovementType.SALE_OUT,
                quantity=Decimal("1000"),
            )

    def test_average_cost_is_weighted(self):
        record_movement(
            item=self.item, movement_type=MovementType.PURCHASE_IN,
            quantity=Decimal("100"), unit_cost=Decimal("12000"),
        )
        self.item.refresh_from_db()
        # 100 at 8,000 plus 100 at 12,000 is 200 at 10,000
        self.assertEqual(self.item.average_cost, Decimal("10000.00"))

    def test_balance_after_matches_the_item(self):
        movement = record_movement(
            item=self.item, movement_type=MovementType.SALE_OUT, quantity=Decimal("7"),
        )
        self.item.refresh_from_db()
        self.assertEqual(movement.balance_after, self.item.quantity_on_hand)

    def test_ledger_rebuilds_the_running_total(self):
        record_movement(item=self.item, movement_type=MovementType.SALE_OUT, quantity=Decimal("9"))
        self.item.refresh_from_db()
        expected = self.item.quantity_on_hand
        self.item.quantity_on_hand = Decimal("0")   # pretend it drifted
        self.item.save(update_fields=["quantity_on_hand"])
        self.assertEqual(self.item.recalculate_quantity(), expected)


class LowStockRule(Base):
    """BUG: an item with no minimum counted as low on one screen, not on another."""

    def test_item_without_a_minimum_is_not_running_out(self):
        loose = self.make_item("No minimum set", minimum=0)
        self.assertFalse(loose.is_below_minimum)

    def test_every_screen_agrees_about_what_is_running_out(self):
        from inventory.dashboard import stock_alerts
        from accounts.context_processors import _badge_counts

        self.make_item("No minimum set", minimum=0)
        low = self.make_item("Nearly gone", minimum=20)
        record_movement(
            item=low, movement_type=MovementType.OPENING,
            quantity=Decimal("5"), unit_cost=Decimal("100"),
        )

        by_property = {i.pk for i in Item.objects.all() if i.is_below_minimum}
        by_dashboard = {r["item"].pk for r in stock_alerts(limit=99)["rows"]}
        self.assertEqual(by_property, by_dashboard)
        self.assertEqual(_badge_counts()["low"], len(by_property))


class LandedCost(Base):
    def test_charges_are_spread_and_none_is_lost(self):
        """BUG: rounding each line separately quietly lost shillings."""
        other = self.make_item("Cutting Disc")
        purchase = Purchase.objects.create(
            supplier=self.supplier, currency="USD", exchange_rate=Decimal("2600"),
            freight_cost=Decimal("100000"), customs_duty=Decimal("33333"),
            allocation_method=AllocationMethod.BY_VALUE,
        )
        PurchaseLine.objects.create(purchase=purchase, item=self.item,
                                    quantity=Decimal("3"), unit_price=Decimal("3.33"))
        PurchaseLine.objects.create(purchase=purchase, item=other,
                                    quantity=Decimal("7"), unit_price=Decimal("1.11"))
        purchase.receive(user=self.manager)

        spread = sum(line.allocated_charges for line in purchase.lines.all())
        self.assertEqual(spread, purchase.additional_charges)

    def test_a_line_with_no_quantity_is_refused_with_a_message(self):
        """BUG: it divided by zero and threw a raw Decimal error at the user."""
        purchase = Purchase.objects.create(supplier=self.supplier)
        PurchaseLine.objects.create(purchase=purchase, item=self.item,
                                    quantity=Decimal("0"), unit_price=Decimal("5000"))
        with self.assertRaises(ValueError) as caught:
            purchase.receive(user=self.manager)
        self.assertIn("greater than zero", str(caught.exception))

    def test_receiving_twice_is_refused(self):
        purchase = Purchase.objects.create(supplier=self.supplier)
        PurchaseLine.objects.create(purchase=purchase, item=self.item,
                                    quantity=Decimal("10"), unit_price=Decimal("9000"))
        purchase.receive(user=self.manager)
        with self.assertRaises(ValueError):
            purchase.receive(user=self.manager)


class SalesFlow(Base):
    def test_stock_moves_on_delivery_not_on_the_invoice(self):
        before = self.item.quantity_on_hand
        invoice = self.invoice_for(5)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, before)

        note = invoice.create_delivery_note(user=self.manager)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, before)

        note.confirm_delivery(user=self.manager)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, before - 5)

    def test_one_invoice_cannot_deliver_the_same_goods_twice(self):
        """BUG: five bearings left the store as ten."""
        before = self.item.quantity_on_hand
        invoice = self.invoice_for(5)
        invoice.create_delivery_note(user=self.manager).confirm_delivery(user=self.manager)

        with self.assertRaises(ValueError):
            invoice.create_delivery_note(user=self.manager)

        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, before - 5)

    def test_asking_twice_before_delivery_returns_the_same_note(self):
        invoice = self.invoice_for(5)
        first = invoice.create_delivery_note(user=self.manager)
        second = invoice.create_delivery_note(user=self.manager)
        self.assertEqual(first.pk, second.pk)

    def test_confirming_a_delivery_twice_is_refused(self):
        invoice = self.invoice_for(5)
        note = invoice.create_delivery_note(user=self.manager)
        note.confirm_delivery(user=self.manager)
        with self.assertRaises(ValueError):
            note.confirm_delivery(user=self.manager)

    def test_payments_add_up_and_move_the_status(self):
        invoice = self.invoice_for(5)
        total = invoice.grand_total
        Payment.objects.create(invoice=invoice, amount=total / 2)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PART_PAID")
        Payment.objects.create(invoice=invoice, amount=total / 2)
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, "PAID")
        self.assertEqual(invoice.balance_due, Decimal("0.00"))

    def test_profit_uses_what_the_goods_cost_us(self):
        invoice = self.invoice_for(5)
        self.assertEqual(invoice.cost_of_sale, Decimal("5") * self.item.average_cost)
        self.assertEqual(invoice.gross_profit, invoice.subtotal - invoice.cost_of_sale)


class Workshop(Base):
    def test_parts_leave_the_store_only_once(self):
        job = JobCard.objects.create(customer=self.customer, title="Bearing swap")
        material = JobMaterial.objects.create(job=job, item=self.item, quantity=Decimal("4"))
        material.issue(user=self.manager)
        with self.assertRaises(ValueError):
            material.issue(user=self.manager)
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_on_hand, Decimal("96.000"))

    def test_a_job_is_late_only_when_it_is_still_open(self):
        yesterday = timezone.now().date() - timezone.timedelta(days=1)
        job = JobCard.objects.create(
            customer=self.customer, title="Late one", due_date=yesterday
        )
        self.assertTrue(job.is_overdue)
        job.status = "COMPLETED"
        self.assertFalse(job.is_overdue)


class Screens(Base):
    def setUp(self):
        super().setUp()
        self.client = Client()

    def test_the_adjustment_message_reports_the_new_quantity(self):
        """BUG: it read the form's stale copy and announced the old number."""
        self.client.force_login(self.manager)
        response = self.client.post(reverse("inventory:stock_adjust"), {
            "item": self.item.pk,
            "movement_type": MovementType.ADJUSTMENT_OUT,
            "quantity": "3",
            "movement_date": timezone.now().date().isoformat(),
        }, follow=True)
        self.item.refresh_from_db()
        self.assertContains(response, f"{self.item.quantity_on_hand:g}")

    def test_a_shopkeeper_cannot_reach_the_money(self):
        self.client.force_login(self.shopkeeper)
        for name in ["purchase_list", "report_profit", "report_valuation",
                     "report_movement", "user_list", "briefing"]:
            self.assertEqual(self.client.get(reverse(f"inventory:{name}")).status_code, 403, name)

    def test_a_shopkeeper_does_not_see_cost_on_the_dashboard(self):
        self.client.force_login(self.shopkeeper)
        body = self.client.get(reverse("inventory:dashboard")).content.decode()
        for phrase in ["Value in store", "Money owed to us", "Sold this month"]:
            self.assertNotIn(phrase, body)

    def test_search_finds_an_item_by_its_part_number(self):
        self.item.part_number = "6204-2RS"
        self.item.save()
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("inventory:search") + "?q=6204",
            headers={"x-requested-with": "XMLHttpRequest"},
        )
        titles = [i["title"] for g in response.json()["groups"] for i in g["items"]]
        self.assertTrue(any(self.item.code in t for t in titles))

    def test_the_stock_history_search_does_not_repeat_rows(self):
        """BUG: two querysets ORed together duplicated rows across the join."""
        record_movement(item=self.item, movement_type=MovementType.SALE_OUT,
                        quantity=Decimal("2"))
        self.client.force_login(self.manager)
        response = self.client.get(reverse("inventory:movement_list") + "?q=Bearing")
        shown = response.context["movements"]
        self.assertEqual(len(shown), len(set(m.pk for m in shown)))


class People(Base):
    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.manager)

    def test_the_last_manager_cannot_be_demoted(self):
        response = self.client.post(
            reverse("inventory:user_edit", args=[self.manager.pk]),
            {"first_name": "", "last_name": "", "email": "m@tryvis.co.tz",
             "phone": "", "role": Role.SHOPKEEPER, "is_active": "on"},
            follow=True,
        )
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.role, Role.MANAGER)

    def test_the_last_manager_cannot_be_switched_off(self):
        """BUG: the only way back into setup could be closed from inside it."""
        other = User.objects.create_user("m2", "m2@tryvis.co.tz", "pw", role=Role.MANAGER)
        other.is_active = False
        other.save()
        self.client.post(
            reverse("inventory:user_edit", args=[self.manager.pk]),
            {"first_name": "", "last_name": "", "email": "m@tryvis.co.tz",
             "phone": "", "role": Role.MANAGER},
            follow=True,
        )
        self.manager.refresh_from_db()
        self.assertTrue(self.manager.is_active)

    def test_a_manager_can_reset_a_forgotten_password(self):
        self.client.post(
            reverse("inventory:user_password", args=[self.shopkeeper.pk]),
            {"new_password1": "Bearing6204!", "new_password2": "Bearing6204!"},
        )
        self.shopkeeper.refresh_from_db()
        self.assertTrue(self.shopkeeper.check_password("Bearing6204!"))


class Briefing(Base):
    def test_the_briefing_is_written_without_any_api_key(self):
        from inventory import briefing, dashboard

        data = dashboard.build(self.manager)
        text, source, _ = briefing.get_briefing(data)
        self.assertEqual(source, "system")
        self.assertIn("TZS", text)
        self.assertGreater(len(text), 80)

    def test_the_same_figures_produce_the_same_briefing(self):
        from inventory import briefing, dashboard
        from inventory.models import Briefing as BriefingRecord

        data = dashboard.build(self.manager)
        briefing.get_briefing(data)
        briefing.get_briefing(data)
        self.assertEqual(BriefingRecord.objects.count(), 1)

    def test_every_figure_given_to_the_writer_came_from_the_records(self):
        from inventory import briefing, dashboard

        data = dashboard.build(self.manager)
        facts = briefing.collect_facts(data)
        self.assertEqual(facts["items_kept"], Item.objects.filter(
            is_active=True, item_type__in=[ItemType.STOCK, ItemType.CONSUMABLE]
        ).count())
        self.assertIn("TZS", facts["stock_value"])


class HelpDocument(TestCase):
    """The assistant's training material is fetched by a bot, not a person."""

    def test_anyone_can_fetch_it_without_signing_in(self):
        response = Client().get("/help/knowledge.txt")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response["Content-Type"].startswith("text/plain"))

    def test_it_carries_no_business_data(self):
        body = Client().get("/help/knowledge.txt").content.decode()
        for leak in ["SECRET_KEY", "DB_PASSWORD", "XAI_API_KEY", "postgres"]:
            self.assertNotIn(leak, body)

    def test_the_persona_is_served_separately_from_the_training(self):
        """The behaviour rules belong in the system prompt, not in the chunks."""
        persona = Client().get("/help/assistant.txt").content.decode()
        training = Client().get("/help/knowledge.txt").content.decode()
        self.assertIn("cannot see their database", persona)
        self.assertNotIn("cannot see their database", training)
        self.assertIn("**Q:", training)

    def test_a_token_closes_the_link_when_one_is_set(self):
        with self.settings(HELP_DOC_TOKEN="shhh"):
            for path in ("/help/knowledge.txt", "/help/assistant.txt"):
                self.assertEqual(Client().get(path).status_code, 404)
                self.assertEqual(Client().get(f"{path}?k=shhh").status_code, 200)


class PrintedDocuments(Base):
    """What the customer actually hands over. Regressions here are visible to their clients."""

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.client.force_login(self.manager)

    def test_colours_survive_the_print_button(self):
        """BUG: browsers drop background colours unless told not to — the invoice printed grey."""
        invoice = self.invoice_for(3)
        body = self.client.get(f"/app/print/invoice/{invoice.pk}/").content.decode()
        self.assertIn("print-color-adjust: exact", body)

    def test_a_long_invoice_is_never_cut_off_when_printed(self):
        """BUG: a fixed-height page with overflow hidden silently dropped the last lines and the total."""
        body = self.client.get(f"/app/print/invoice/{self.invoice_for(3).pk}/").content.decode()
        print_css = body[body.index("@media print"):]
        print_css = print_css[:print_css.index("}\n  }") + 1]
        self.assertNotIn("overflow: hidden", print_css)
        self.assertNotIn("height: 296mm;", print_css.replace("min-height: 296mm;", ""))

    def test_the_pdf_link_gives_the_same_page_as_print(self):
        invoice = self.invoice_for(3)
        response = self.client.get(f"/app/print/invoice/{invoice.pk}/?pdf=1")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "html2pdf.bundle.min.js")
        self.assertContains(response, 'filename: "' + invoice.reference + '.pdf"')

    def test_the_efd_qr_appears_on_the_printed_invoice(self):
        invoice = self.invoice_for(3)
        invoice.efd_qr_image = "data:image/png;base64,iVBORw0KGgo="
        invoice.efd_receipt_number = "Z-04417-0003281"
        invoice.save()
        body = self.client.get(f"/app/print/invoice/{invoice.pk}/").content.decode()
        self.assertIn("Z-04417-0003281", body)
        self.assertIn("data:image/png;base64,iVBORw0KGgo=", body)
