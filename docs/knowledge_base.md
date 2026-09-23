# TRYVIS INVENTORY — HELP KNOWLEDGE BASE

Training material for the Tryvis support assistant on JamiiBot.
Questions and answers on purpose: people ask the assistant questions, so the
material it searches should be shaped like questions too.

The assistant's behaviour rules are NOT in this file. They live in
docs/assistant_persona.md and belong in JamiiBot's system prompt.

---

## GETTING IN

**Q: How do I sign in?**
Open the system's address in the browser, type your username and password, and
press **Sign in**. If you are already signed in, the address takes you straight
to the Dashboard.

**Q: I forgot my password. What do I do?**
Only the Manager can set a new one. Ask them to open **People**, find your name,
press **Password**, and type a new one. They tell you what it is, and you can
change it yourself afterwards from the menu at the top right, under **Change my
password**. There is no email reset — this is an internal system for three people.

**Q: How do I change my own password?**
Press your name at the top right, then **Change my password**. You need your
current password for this one.

**Q: The menu has disappeared on my phone.**
Press the three-line button at the very top left. The menu slides in from the
side. Press the **X** inside it, or tap the dark area beside it, to close it.
On a computer the same button shrinks the menu down to icons only, and the
system remembers your choice.

**Q: Can I use dark mode?**
Yes. Press your name at the top right and choose **Light**, **Dark** or
**Match my device**. The choice is remembered on that device.

---

## THE TWO KINDS OF USER

**Q: What is the difference between a Manager and a Shopkeeper?**
A **Manager** sees everything: what the stock cost, profit, the purchases from
suppliers, all the reports, and the People page.

A **Shopkeeper** does the daily work: items, stock in and out, quotations,
invoices, delivery notes and workshop jobs. They cannot see cost price, profit
or the value of stock anywhere in the system, and pages like **Stock received**
and the reports are closed to them.

**Q: I am a shopkeeper and a page says I am not allowed in.**
That page is for the Manager. It is not a fault. If you need what is on it,
ask the Manager.

**Q: How do I add a new person to the system?**
Manager only. Go to **People**, press **Add a person**, fill in the username,
name, role and first password, then **Save**. Tick **Email them when items run
out** if they should get the daily email — that needs an email address.

**Q: Someone has left the company. Do I delete them?**
No — switch them off. Open **People**, press **Edit** on their name, untick
**Can sign in**, and save. Deleting them would break the record of who did what;
switching them off keeps the history and stops them signing in.

**Q: Why can't I change my own role?**
The system stops you, so that nobody can lock themselves out of their own
system by accident. It also refuses to remove or switch off the last remaining
Manager, because then nobody could reach the setup pages at all.

---

## THE DASHBOARD

**Q: What am I looking at on the Dashboard?**
The top line is the briefing — a few sentences on how the business stands today.
Below it are the numbers: items you keep, value in the store, items running out,
workshop jobs, quotations waiting, money owed to you, and what has sold this
month. Then the health of the store, the items to order, the charts, what just
happened, and what needs someone to act.

**Q: What is the circle with a percentage?**
The health of the store. It is the share of your items that are at a
comfortable level. The four lines beside it break it down: fine, getting low,
almost finished, and finished.

**Q: What counts as "almost finished"?**
An item that has fallen to half of its alert level or less. "Getting low" is
anything at or below the alert level but above that halfway point. "Finished"
means nothing at all on the shelf.

**Q: What is the briefing at the top?**
A short written summary of the day, produced from your own figures. Press
**See the figures this was written from** to see every number it used. If you
want a fresh one, press **Rewrite**.

**Q: Is the briefing written by AI?**
Sometimes. If the company has connected an AI key, the AI phrases it. If not,
the system writes it itself. Either way the figures are calculated by the
system first — the writer is only given finished numbers and is not allowed to
work out new ones. That is why you can always check it against the figures page.

---

## ITEMS

**Q: How do I add a new item?**
Go to **All items** and press **Add item**. Fill in the name, choose the group,
choose how it is sold (pieces, kilograms, metres), and set the alert level.
Press **Save**. The item code is made for you.

**Q: Where does the item code come from?**
The system makes it from the group you choose: company letters, group letters,
then a number. For example a bearing becomes `TIL-BRG-001`, the next one
`TIL-BRG-002`. You never type it yourself and no two items can ever share one.

**Q: What is the difference between the code and the part number?**
The code is the system's own name for the item. The **part number** is what is
written on the part itself — `6204`, `12B-1`, `E6013`. Always fill it in,
because that is what a customer says on the phone, and the search finds it.

**Q: What do the three kinds of item mean?**
- **For sale** — you buy it to sell it. Bearings, discs, seals.
- **Used in the workshop** — consumables used on jobs. Welding rods, grease.
- **Service — nothing on the shelf** — labour, machining. It can go on a
  quotation or an invoice, but the system keeps no stock for it.

**Q: What is the alert level?**
The number at which the item counts as running out. When stock falls to it or
below, the item appears under **Running out**, the badge on the menu goes up,
and it is included in the daily email. Leave it at zero and the system will
never warn you about that item.

**Q: What is "Order this many"?**
How much you normally buy at a time. It appears on the **Running out** report as
a suggestion, so whoever places the order does not have to think about it.

**Q: How do I find an item quickly?**
Use the search box at the top of any page — it looks through item names, codes,
part numbers, customers, invoices, quotations and jobs at once. On a computer,
Ctrl and K jumps straight into it. Or go to **All items** and use the search
and group filter there.

**Q: Can I delete an item?**
No, and that is deliberate. An item that has ever moved is part of the history —
deleting it would leave the stock history pointing at nothing. Instead open the
item, press **Edit**, and untick **Still in use**. It disappears from the lists
and stops being counted, and the history stays intact.

**Q: What does the line on an item's page show?**
How much of that item has been in the store over time, taken straight from the
movement history. If it steps down often and never comes back up, you are not
reordering it enough.

---

## STOCK COMING IN

**Q: I received goods from a supplier. What do I do?**
Manager only. Go to **Stock received**, press **Record new stock**, choose the
supplier and date, enter the shipping and customs costs, then list the items
with how many and the price each. Press **Save**. Nothing has entered stock yet.
Check the lines, then press **Add to store**.

**Q: Why two steps? Why not add it straight away?**
Because once it is in the store, the cost of every piece changes. The system
lets you check the lines first. Once you press **Add to store** it cannot be
undone — a mistake has to be corrected with a stock adjustment.

**Q: What are shipping, customs and clearing for?**
For goods from outside Tanzania, the supplier's price is not what the item
really costs you. Those charges are entered on the top of the page and then
spread across the items when you add them to the store. The result is the
**Real cost each** column — that is the figure the system uses for every profit
calculation, not the supplier's price.

**Q: What does "Share these extra costs" mean?**
How the shipping and customs are divided between the items on the page.
- **By price** — expensive items carry more of the cost. This is the usual choice.
- **By quantity** — every piece carries the same share.
- **By weight** — heavy items carry more. Use it when the freight bill was
  charged by weight. You must then fill in the weight column.

**Q: I paid in dollars. What do I enter?**
Put `USD` in the currency box and today's rate in "1 of that currency = how many
TZS". Enter the supplier's prices in dollars, exactly as on their invoice. The
system converts everything to shillings for you.

**Q: I paid in shillings.**
Leave the currency as `TZS` and put `1` as the rate. The system will refuse any
other rate with TZS, to stop a wrong conversion slipping through.

**Q: The system refuses to add my goods to the store.**
Usually one of two things: a line has no quantity, or the purchase has already
been added. The message names the item.

---

## STOCK GOING OUT, AND FIXING THE COUNT

**Q: When does stock actually leave the store?**
Only when you confirm a delivery note, or when you take parts out for a
workshop job. Raising an invoice does not move stock — an invoice can be
written days before the customer collects.

**Q: I counted the shelf and the number is wrong. What do I do?**
Go to **Fix stock count**, choose the item, choose what happened, enter how
many, and save. Use **"I counted and found less than the system says"** if the
shelf has fewer than the screen, and **"I counted and found more"** if it has
more. Write the reason — in six months somebody will want to know.

**Q: I am entering an item for the first time and it already has stock.**
Choose **"Starting stock — first time entering this item"** and put what is on
the shelf. You also need the cost of one piece, otherwise the system has no
cost to work profit from.

**Q: A customer returned something.**
**Fix stock count**, and choose **"Customer brought something back"**. It goes
back into the store.

**Q: Can I edit or delete a movement in the stock history?**
No. Nothing in the history is ever changed or removed — that is what makes it
worth trusting. A mistake is corrected by recording the opposite movement, and
both entries stay visible.

**Q: The system says there is not enough stock.**
You are trying to take out more than the system thinks is there. Either the
count is wrong — fix it under **Fix stock count** — or the quantity you typed
is wrong. The system will not let stock go below zero.

---

## QUOTATIONS, INVOICES AND DELIVERY NOTES

**Q: What is the normal order of work?**
Quotation → Invoice → Delivery note.
1. **Quotation** — the price you give the customer. Nothing moves.
2. **Invoice** — the bill, once they agree. Still nothing moves.
3. **Delivery note** — the goods leaving. When you confirm it, stock comes down.

**Q: How do I make a quotation?**
**Quotations** → **New quotation**. Choose the customer, set the date and how
long the price is good for, then add the lines: item, quantity, price each, and
a discount if you are giving one. Save.

**Q: The customer agreed. What now?**
Open the quotation and press **Convert to invoice**. All the lines are copied
across, and the quotation is marked as turned into an invoice so nobody
quotes it twice.

**Q: How do I send the goods?**
Open the invoice and press **Create delivery note**. Print it, send the goods
with it, and when the customer has taken them, open the note and press
**Confirm the customer took the goods**. That is the moment stock comes down.

**Q: I pressed Create delivery note twice.**
The system gives you back the same note, not a second one. And once a note is
confirmed, it refuses to make another for that invoice — otherwise the same
goods would leave the store twice on paper.

**Q: The customer paid. Where do I record it?**
Open the invoice, and at the bottom enter how much they paid, the date, and how
they paid it. The system adds it up, updates what is still owed, and marks the
invoice part paid or paid on its own.

**Q: How do I print a document?**
Open the quotation, invoice or delivery note and press **Print**. It opens laid
out for A4 with the company header and signature spaces. **PDF** gives you a
file you can attach to an email.

**Q: Why does the delivery note not show prices?**
On purpose. The person receiving the goods signs for what arrived, not for what
it cost. The prices are on the invoice.

**Q: What is VAT here?**
18%, added unless you untick **Add VAT** on the document. If your prices already
include VAT, tick **Prices already include VAT** and the system works backwards
instead of adding it on top.

---

## WORKSHOP JOBS

**Q: What is a job card for?**
A piece of work in the workshop. It records the parts used, the hours worked,
and what you charged — so afterwards you can see whether the job actually made
money.

**Q: How do I open a job?**
**Workshop jobs** → **New job**. Choose the customer, describe the work, say
which machine, set the date you promised it, and list the parts you expect to
use. Save.

**Q: I listed the parts but stock has not changed.**
Correct. Listing a part is a plan. Open the job and press **Take these parts
from the store** when you actually take them off the shelf. Only then does
stock move, and the cost is fixed at what the part costs that day.

**Q: What does "Promised to customer by" do?**
It is the date you told the customer. Jobs past that date appear in red as
**Late** on the job list and on the Dashboard, so nothing quietly slips.

**Q: Where do I see whether a job made money?**
Manager only. The job page shows parts used, labour, total cost and profit. The
job list shows the same for every job, and there is a chart of profit per job
with losses drawn below the line.

---

## CUSTOMERS, SUPPLIERS, GROUPS AND UNITS

**Q: How do I add a customer?**
**Customers**, fill the form on the right, save. Name is enough to start, but
add the TIN if you will be invoicing them properly.

**Q: How do I add a supplier?**
Manager only, under **Suppliers**. Tick **Goods come from outside Tanzania** for
foreign suppliers — that is a reminder that their purchases carry shipping and
customs.

**Q: What are Groups?**
Categories of item — Bearings, Cutting & Grinding, Seals. The group gives each
item the middle part of its code and is used in the reports. Manager only,
under **Groups**. The three-letter code cannot be changed once items are using it.

**Q: What are Units?**
How an item is sold: pieces, kilograms, metres, litres, hours. Manager only,
under **Units**.

---

## REPORTS

**Q: What sells, what sits — what does it tell me?**
How each item moves over the last ninety days. **Sells fast**, **Normal**,
**Sells slowly**, **Not selling**. The number that matters most is the money
stuck in items nobody has bought — that is cash sitting on a shelf doing
nothing. Either discount them or stop reordering them.

**Q: Value of stock.**
What everything on the shelf is worth, at what it cost you, broken down by
group and by the biggest single holdings. This is the figure an accountant asks
for at year end.

**Q: Profit.**
Invoice by invoice: what you charged, what the goods cost, and the difference.
It uses the real cost including shipping and customs, so the number is honest.
Change the number of days at the top to look at a different period.

**Q: Running out.**
Everything below its alert level, how far below, and how much it would cost to
restock. This is the page to have open when you phone a supplier.

**Q: Can a shopkeeper see the reports?**
Only **Running out**. Everything else shows cost or profit, so it is Manager only.

---

## THE DAILY EMAIL

**Q: What is the email about items running out?**
Every weekday morning the system emails a list of items at or below their alert
level, to whoever is ticked for it under **People**.

**Q: Why did an item stop appearing in the email?**
Each item is reported once. It goes quiet until it has been restocked above its
alert level and falls back down again, so the email stays worth opening.

**Q: We are not getting the email.**
Check three things: the people who should get it are ticked under **People**,
they have an email address on their account, and the items have an alert level
above zero. If all three are right, tell William — it is a setting on the server.

---

## WHEN SOMETHING LOOKS WRONG

**Q: The stock on screen does not match the shelf.**
Count it, then go to **Fix stock count** and record the difference with a
reason. Then look at the item's history to see where it drifted — usually
goods that arrived without being recorded, or parts taken for a job without
being issued.

**Q: A profit figure looks too good.**
Check whether the purchase that brought those goods in had its shipping and
customs entered. If they were left out, the goods look cheaper than they were
and the profit looks bigger than it is.

**Q: An item shows no cost at all.**
It has never been received through **Stock received**, and no cost was entered
when it was first added. Use **Fix stock count** with "Starting stock" and put
the real cost of a piece.

**Q: Something I expected to see is not there.**
Check you are signed in as the right person — a lot of what the Manager sees is
hidden from a Shopkeeper by design.

**Q: The page says I am not allowed.**
It is a Manager page. Not a fault.

---

## THINGS THE SYSTEM DELIBERATELY DOES NOT DO

Explain these rather than looking for a way around them.

- Stock history is never edited or deleted. Mistakes are corrected with an
  opposite movement, and both stay visible.
- An item that has moved cannot be deleted, only switched off.
- One invoice cannot deliver the same goods twice.
- A purchase cannot be added to the store twice.
- Stock cannot go below zero.
- The last Manager cannot be demoted or switched off.
- Shopkeepers cannot see cost or profit anywhere, including in search results
  and printed documents.

---

## WHEN TO SEND SOMEONE TO WILLIAM

Tell them to contact William at JamiiTek when:

- something is broken, blank, or shows an error message
- they need a new feature, or a report the system does not have
- the daily email is not arriving and the three checks above are all fine
- they want a user removed rather than switched off
- they need the data exported, backed up, or moved

Do not attempt to diagnose server problems, database problems or anything to do
with hosting.
