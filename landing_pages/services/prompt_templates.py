"""Prompt construction for the landing-page AI generator.

One ``system`` prompt (constant) plus a per-page-type ``user`` prompt
builder. The system prompt pins Claude to EchoDesk's real functionality
inventory so copy can only reference shipped capabilities. The tool-use
schema in ``ai_landing_generator.LANDING_PAGE_TOOL`` enforces structure
server-side.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from landing_pages.models import LandingTopic


SYSTEM_PROMPT = """You draft high-conversion landing pages for EchoDesk — an \
all-in-one business platform for Georgian small- and mid-size businesses. \
Every landing page is bilingual (Georgian + English) and ends with a CTA to \
/registration for a free trial.

EchoDesk ships the following modules. You may ONLY reference capabilities \
from this list — do not invent features.

1. **WhatsApp** — Cloud API + Business App connection, MARKETING / UTILITY / \
   AUTHENTICATION message templates, approved Georgian templates, media \
   attachments, 80 msg/sec throughput, interactive (button / list) messages, \
   unified inbox with Messenger / Instagram / email / calls.
2. **Facebook Messenger** — Two-way conversations, sent / delivered / read \
   receipts, attachments, story replies.
3. **Instagram** — Direct messages + story replies, two-way.
4. **TikTok Shop** — Connected shop accounts, two-way DMs with buyers.
5. **Email** — IMAP/SMTP two-way sync, thread grouping, seen / flagged / \
   labeled states, multiple connections per tenant, attachments, Georgian \
   font support.
6. **PBX / call center** — Asterisk 20.6, SIP queues (rrmemory strategy), \
   call recording (MixMonitor), voicemail, working-hours routing, call \
   forwarding, per-user extensions, custom greetings, Georgian SIP trunk \
   pre-configured (89.150.1.11).
7. **Tickets** — Kanban columns, tags, priorities, per-ticket payment \
   tracking, assignment, comments.
8. **Invoices** — Draft → Sent → Viewed → Paid states, line items, tax + \
   discount, recurring invoices with saved-card retry, GEL-native, \
   IBAN / SWIFT fields, Bank of Georgia (BOG) OAuth2 integration, ecommerce \
   orders API.
9. **Bookings** — Calendar, service categories, per-service slots, payments \
   per booking, multilingual (ka / ru / en) booking forms.
10. **Leave management** — Types (Vacation / Sick / Personal), manager + \
    optional HR approval workflow, accrual vs annual, Georgian labor-calendar \
    holidays.
11. **Pricing** — Feature-based (not per-seat), GEL-native, a la carte \
    module selection per tenant.

**Hard rules — do NOT violate:**

1. Do NOT invent specific prices, plan tiers, or numeric limits for \
   competitors. When comparing, use hedged language ("typically", "in most \
   plans") and focus on structural differences (GEL vs USD, Georgian-hosted \
   vs abroad, feature-based vs per-seat pricing).
2. Do NOT claim SLAs, escalation rules, macros, saved replies, call \
   analytics dashboards, or AI auto-routing — these are not modeled in the \
   product.
3. Lead with a concrete Georgian-SMB pain point in ``hero_subtitle`` and \
   the first content block (benefit_grid or checklist). Product is the \
   solution revealed through the body, not the opening line.
4. All prices in GEL (ლარი). Never quote USD.
5. Tone: honest, specific, concrete. No generic SaaS buzzwords \
   ("revolutionize", "game-changing", "world-class"). Write like you'd \
   speak to a salon owner in Tbilisi.
6. Georgian content must read as native Georgian — do not translate \
   word-for-word from the English version. Both locales must be present \
   and non-empty.
7. The last FAQ answer or the final content block MUST carry a CTA to \
   ``/registration``. Phrasing: Georgian "დაიწყე უფასო ცდა" / \
   English "Start free trial".
8. Natural keyword usage — never keyword-stuff. Target keywords are for \
   weaving in organically.

**Block types you can use in content_blocks:**

- ``benefit_grid``: 3-6 items, each with icon (Lucide icon name), \
  title, description. Use for "Why EchoDesk for this feature".
- ``checklist``: 3-10 items with text only. Use for "What you get out \
  of the box" — concrete, scannable deliverables.
- ``feature_showcase``: heading + feature_slug + deep body paragraph \
  (>=50 chars per locale). Use to zoom in on the primary feature.

You must call the ``save_landing_page`` tool with the full bilingual \
payload. No text outside the tool call.
"""


def _keywords_or_hint(topic: "LandingTopic") -> str:
    return ", ".join(topic.target_keywords or []) or "(infer 3-5 naturally)"


def build_user_prompt(topic: "LandingTopic") -> str:
    """Route per page_type. Keep each branch concrete and actionable."""

    keywords = _keywords_or_hint(topic)
    title_ka = topic.get_title_hint("ka") or "(propose)"
    title_en = topic.get_title_hint("en") or "(propose)"
    highlighted = ", ".join(topic.highlighted_feature_slugs or []) or "(none specified)"

    base = f"""Draft a landing page with the brief below.

- Page type: {topic.page_type}
- Primary language target: {topic.primary_language} (both locales are \
generated regardless; lean the angle toward this audience)
- Slug: {topic.slug}
- Title hints (refine as needed):
  - Georgian: {title_ka}
  - English: {title_en}
- Angle: {topic.angle_hint or "(infer from the slug and page_type)"}
- Target keywords to weave in naturally: {keywords}
- Highlighted feature slugs: {highlighted}
"""

    if topic.page_type == "feature":
        base += """
Task: Draft a landing page for the specified EchoDesk feature module, aimed \
at Georgian SMBs who are actively comparing tools.

Use these block kinds in content_blocks (in this order):

1. ``benefit_grid`` — heading like "რატომ EchoDesk?" / "Why EchoDesk for \
   this". 3-6 items answering *why this feature, specifically inside \
   EchoDesk*, for a Georgian SMB. Concrete wedges: GEL billing, \
   Georgian-hosted, bundled with the rest of the platform, native Georgian \
   UI, etc.
2. ``checklist`` — heading like "რას იღებ" / "What you get out of the box". \
   3-10 items. Each item is a specific deliverable — not abstract benefits. \
   (e.g. "Approved MARKETING / UTILITY / AUTH WhatsApp templates", not \
   "better messaging".)
3. ``feature_showcase`` — set ``feature_slug`` to the primary highlighted \
   feature (from the list above, or the feature this page is about). Body \
   paragraph (>= 50 chars per locale) that digs deeper into one specific \
   workflow or integration detail.

FAQ: 3-8 items covering the top search-intent questions for this feature \
in Georgia. Last answer should include the CTA to /registration.

og_tag: a short 1-2 word chip identifying the module \
(e.g. "WhatsApp", "Invoicing", "Call Center", "Bookings").
"""
    elif topic.page_type == "vertical":
        base += """
Task: Position EchoDesk as the right tool for the specified vertical \
(industry) in Georgia. Target readers: owners or ops managers of that \
kind of business.

Use these block kinds in content_blocks (in this order):

1. ``benefit_grid`` — heading framing what makes running *this kind of \
   business in Georgia* hard, and how a bundled all-in-one platform solves \
   it. 3-6 items. Lead with the pain — e.g. "სალონები იყენებენ 5 ცალკე \
   ხელსაწყოს" → "Salons juggle 5 separate tools".
2. ``checklist`` — heading like "რა გაქვს ერთ სისტემაში" / "What's in one \
   system". 3-10 items listing the bundled modules relevant to this \
   vertical (from the highlighted_feature_slugs list).
3. ``feature_showcase`` — pick the single most-important module for this \
   vertical (set ``feature_slug`` accordingly) and write a body paragraph \
   showing a concrete workflow for this type of business.

FAQ: 3-8 items answering questions a business owner in this vertical would \
actually search. Last answer carries the CTA to /registration.

og_tag: the vertical name, 1-2 words \
(e.g. "Salons", "Law firms", "E-commerce", "Clinics").
"""
    elif topic.page_type == "comparison":
        competitor = topic.competitor_name or "the competitor"
        base += f"""
Competitor: {competitor}

Task: Honest comparison page — EchoDesk vs {competitor}. Georgian SMB \
audience. Do NOT invent specific {competitor} prices or feature names. \
When referencing a {competitor} capability you're unsure about, use hedged \
language ("typically", "in most plans").

Use these block kinds in content_blocks (in this order):

1. ``benefit_grid`` — heading like "როდის აჯობებს EchoDesk" / "Where \
   EchoDesk fits better". 3-6 items highlighting EchoDesk's structural \
   wedges vs {competitor} — GEL billing, Georgian hosting, bundled SIP + \
   invoicing + bookings, feature-based pricing, native Georgian UI.
2. ``checklist`` — heading like "რომელი ავირჩიო?" / "When to pick which". \
   Structure items as scenario-based decision hints. Include at least 2-3 \
   scenarios where {competitor} is the better pick (honest acknowledgement \
   of competitor strengths: bigger global community, deeper marketplace, \
   etc. — but don't invent specifics).
3. ``feature_showcase`` — pick one EchoDesk module where the gap vs \
   {competitor} is structurally biggest (e.g. call-center bundling, GEL \
   invoicing, Georgian-hosted email). Set ``feature_slug`` to that module. \
   Body paragraph (>= 50 chars per locale) giving concrete detail.

FAQ: 3-8 items, cover questions like "Can I migrate data from {competitor} \
to EchoDesk?", "Is EchoDesk cheaper in Georgia?", "Does EchoDesk support \
Georgian language?". Last answer carries the CTA to /registration.

og_tag: "vs {competitor}" or similar short chip.
"""
    else:
        # Unknown page_type — best-effort generic prompt.
        base += """
Task: Draft a generic landing page with benefit_grid + checklist + \
feature_showcase blocks. FAQ 3-8 items. Last FAQ answer carries CTA to \
/registration.
"""

    base += (
        "\nCall the save_landing_page tool with the full bilingual payload. "
        "Do not return any text outside the tool call."
    )
    return base
