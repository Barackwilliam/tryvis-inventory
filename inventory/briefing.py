"""
The written briefing.

Rule that governs this whole module: **the model never does arithmetic and
never sees the database.** Python works out every figure from real records,
hands the model a small sheet of finished numbers, and the model's only job is
to turn them into readable paragraphs. So the briefing can be badly worded on a
bad day, but it cannot be wrong about the business.

Three layers, in order:

1. `collect_facts()`  – plain numbers, all derived, nothing invented.
2. `write_locally()`  – a briefing written in Python. No network, no key, no
                        cost. This is what the client reads if anything at all
                        goes wrong upstream.
3. `write_with_grok()`– the same facts, phrased by xAI. Used when a key is set.

The result is cached against a fingerprint of the facts, so opening the
dashboard ten times in a morning makes at most one API call.
"""
import json
import hashlib
import logging
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

XAI_URL = "https://api.x.ai/v1/chat/completions"

SYSTEM_PROMPT = """You write the daily briefing for the manager of Tryvis \
Investments Limited, an engineering supply company in Dar es Salaam. They sell \
bearings, seals, cutting discs and drive parts, and they run a workshop.

You are given a sheet of figures that have already been calculated from the \
company's records. Follow these rules exactly:

- Use ONLY the figures in the sheet. Never calculate a new number, never \
estimate, never guess a trend that is not given to you.
- If something is not in the sheet, do not mention it.
- Write for a busy manager, not an analyst. Short sentences. Plain English, \
the way a good shop supervisor talks. No jargon, no bullet symbols, no headings.
- Three short paragraphs, 150 words in total at the very most.
  Paragraph 1: how the business stands right now.
  Paragraph 2: the one or two things that need attention today, and why.
  Paragraph 3: one concrete suggestion, drawn only from the figures given.
- Money is Tanzanian shillings. Write them as "TZS 4,093,200".
- Never invent product names, customer names or dates.
- Do not greet the reader and do not sign off. Start with the substance."""


# --------------------------------------------------------------- the facts
def _money(value):
    return f"TZS {Decimal(value or 0):,.0f}"


def collect_facts(data):
    """
    Turn the dashboard's data into a flat sheet of finished statements.

    `data` is whatever `inventory.dashboard.build()` returned, so the briefing
    and the screen can never disagree with each other.
    """
    from inventory.reports import movement_analysis

    health = data["health"]
    alerts = data["alerts"]
    sales = data["sales"]
    quotations = data["quotations"]
    workshop = data["workshop"]

    facts = {
        "date": data["today"].strftime("%d %B %Y"),
        "items_kept": data["item_count"],
        "stock_value": _money(data["stock_value"]),
        "stock_health_percent": health["score"],
        "stock_health_verdict": health["verdict"],
        "items_fine": health["bands"][0].count,
        "items_getting_low": health["bands"][1].count,
        "items_almost_finished": health["bands"][2].count,
        "items_finished": health["bands"][3].count,
        "items_to_reorder": alerts["total"],
        "sales_this_month": _money(sales["this_month"]),
        "sales_last_month": _money(sales["last_month"]),
        "money_owed_to_us": _money(sales["outstanding"]),
        "unpaid_invoices": sales["unpaid_count"],
        "invoices_past_due_date": sales["overdue_count"],
        "value_past_due_date": _money(sales["overdue_value"]),
        "money_collected_this_month": _money(sales["collected_this_month"]),
        "quotations_waiting_on_customer": quotations["waiting"],
        "value_of_those_quotations": _money(quotations["waiting_value"]),
        "expired_quotations": quotations["expired"],
        "workshop_jobs_open": workshop["active"],
        "workshop_jobs_late": workshop["overdue"],
        "workshop_jobs_due_today": workshop["due_today"],
        "workshop_jobs_finished_this_month": workshop["completed_this_month"],
        "deliveries_not_yet_handed_over": len(data["pending_deliveries"]),
    }

    if data["stock_value_change"] is not None:
        facts["stock_value_change_percent"] = round(data["stock_value_change"], 1)
    if sales["change"] is not None:
        facts["sales_change_percent_vs_last_month"] = round(sales["change"], 1)

    # the three items most in need of an order
    facts["items_needing_an_order"] = [
        {
            "name": row["item"].name,
            "code": row["item"].code,
            "in_stock": f"{row['item'].quantity_on_hand:g} {row['item'].unit}",
            "should_not_fall_below": f"{row['item'].minimum_level:g}",
            "state": row["label"],
        }
        for row in alerts["rows"][:3]
    ]

    # what moves and what does not
    try:
        rows = movement_analysis(days=90)
        facts["best_sellers_last_90_days"] = [
            {"name": r.item.name, "sold": f"{r.quantity_sold:g}"}
            for r in rows if r.classification == "FAST"
        ][:3]
        dead = [r for r in rows if r.classification == "DEAD" and r.stock_value > 0]
        facts["items_not_sold_in_90_days"] = len(dead)
        facts["money_stuck_in_unsold_items"] = _money(
            sum((r.stock_value for r in dead), Decimal("0"))
        )
    except Exception:
        logger.exception("movement analysis failed while building the briefing")

    return facts


def fingerprint(facts):
    """Same facts, same briefing. Changes only when the business changes."""
    payload = json.dumps(facts, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]


# ------------------------------------------------------- written in python
def write_locally(facts):
    """
    A real briefing with no AI at all.

    This is not a placeholder. If the key is missing, the network is down or
    xAI changes under us, the manager still opens the dashboard and reads
    something true and useful.
    """
    first = [
        f"You are keeping {facts['items_kept']} item"
        f"{'s' if facts['items_kept'] != 1 else ''}, worth {facts['stock_value']}.",
    ]
    if "stock_value_change_percent" in facts:
        change = facts["stock_value_change_percent"]
        direction = "up" if change >= 0 else "down"
        first.append(f"That is {direction} {abs(change)}% on last month.")
    first.append(
        f"{facts['items_fine']} of them are at a comfortable level "
        f"({facts['stock_health_percent']}% of the store)."
    )
    if facts["sales_this_month"] != "TZS 0":
        first.append(f"Sales so far this month come to {facts['sales_this_month']}.")

    second = []
    if facts["items_to_reorder"]:
        names = ", ".join(i["name"] for i in facts["items_needing_an_order"])
        second.append(
            f"{facts['items_to_reorder']} item"
            f"{'s' if facts['items_to_reorder'] != 1 else ''} need ordering"
            + (f", starting with {names}." if names else ".")
        )
    if facts["invoices_past_due_date"]:
        second.append(
            f"{facts['invoices_past_due_date']} invoice"
            f"{'s are' if facts['invoices_past_due_date'] != 1 else ' is'} past the "
            f"date the customer agreed to pay, holding {facts['value_past_due_date']}."
        )
    elif facts["unpaid_invoices"]:
        second.append(
            f"{facts['unpaid_invoices']} invoices are still unpaid, "
            f"{facts['money_owed_to_us']} in total."
        )
    if facts["workshop_jobs_late"]:
        second.append(
            f"{facts['workshop_jobs_late']} workshop job"
            f"{'s are' if facts['workshop_jobs_late'] != 1 else ' is'} past the "
            f"date you promised the customer."
        )
    if facts["deliveries_not_yet_handed_over"]:
        second.append(
            f"{facts['deliveries_not_yet_handed_over']} delivery note"
            f"{'s are' if facts['deliveries_not_yet_handed_over'] != 1 else ' is'} "
            f"written but the goods have not left the store."
        )
    if not second:
        second.append("Nothing is overdue and nothing is below its minimum level today.")

    third = []
    if facts.get("items_not_sold_in_90_days"):
        third.append(
            f"{facts['money_stuck_in_unsold_items']} is sitting in "
            f"{facts['items_not_sold_in_90_days']} item"
            f"{'s' if facts['items_not_sold_in_90_days'] != 1 else ''} that "
            f"{'have' if facts['items_not_sold_in_90_days'] != 1 else 'has'} not sold in "
            f"three months. Worth deciding whether to discount "
            f"{'them' if facts['items_not_sold_in_90_days'] != 1 else 'it'} or stop reordering."
        )
    elif facts["quotations_waiting_on_customer"]:
        third.append(
            f"{facts['quotations_waiting_on_customer']} quotations worth "
            f"{facts['value_of_those_quotations']} are waiting on customers. "
            f"A phone call is the cheapest sale you will make this week."
        )
    elif facts["items_to_reorder"]:
        third.append("Place the orders above before the next customer asks for them.")
    else:
        third.append("Nothing needs a decision from you this morning.")

    return "\n\n".join([" ".join(first), " ".join(second), " ".join(third)])


# ------------------------------------------------------------ written by ai
def write_with_grok(facts, timeout=20):
    """
    Ask xAI to phrase the facts. Returns None on any problem, and the caller
    falls back to the locally written version — the manager never sees an error
    where the briefing should be.
    """
    api_key = getattr(settings, "XAI_API_KEY", "")
    if not api_key:
        return None

    body = json.dumps({
        "model": getattr(settings, "XAI_MODEL", "grok-4-1-fast"),
        "temperature": 0.3,
        "max_tokens": 400,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content":
                "Today's figures for Tryvis Investments Limited:\n\n"
                + json.dumps(facts, indent=2, default=str)
                + "\n\nWrite the briefing."},
        ],
    }).encode("utf-8")

    request = urllib.request.Request(
        XAI_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = payload["choices"][0]["message"]["content"].strip()
        return text or None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", "ignore")[:300]
        logger.warning("xAI returned %s: %s", error.code, detail)
    except (urllib.error.URLError, TimeoutError) as error:
        logger.warning("could not reach xAI: %s", error)
    except (KeyError, IndexError, ValueError):
        logger.warning("xAI replied in a shape we did not expect")
    return None


# ----------------------------------------------------------------- the api
def get_briefing(data, force=False):
    """
    The briefing for right now, cached against the facts it was written from.

    Returns (text, source, written_at) where source is "grok" or "system".
    """
    from inventory.models import Briefing

    facts = collect_facts(data)
    key = fingerprint(facts)

    if not force:
        cached = Briefing.objects.filter(fingerprint=key).first()
        if cached:
            return cached.text, cached.source, cached.created_at

    text = write_with_grok(facts)
    source = "grok"
    if not text:
        text = write_locally(facts)
        source = "system"

    record = Briefing.objects.create(
        fingerprint=key, text=text, source=source, facts=facts
    )
    # keep the last thirty; this is a briefing, not an archive
    stale = Briefing.objects.order_by("-created_at").values_list("id", flat=True)[30:]
    if stale:
        Briefing.objects.filter(id__in=list(stale)).delete()

    return record.text, record.source, record.created_at
