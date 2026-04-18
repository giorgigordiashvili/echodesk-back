"""Seed the initial BlogTopic queue.

Drops a hand-curated list of ~15 topics so the AI pipeline has a week
or two of runway on a first deploy. Admins can add more through the
Django admin at any time.

Categories:
- 8 competitor comparisons (highest-intent bottom-of-funnel traffic)
- 4 how-to guides (long-tail informational queries)
- 3 use-case narratives (scenario-driven traffic)

Priorities are set so the most competitive-intent content drafts first.
"""

from django.db import migrations


SEED_TOPICS = [
    # ------------------------------------------------------------------
    # Comparison posts — highest priority. One per major competitor.
    # ------------------------------------------------------------------
    {
        "slug": "kommo-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "ka",
        "competitor_name": "Kommo",
        "priority": 100,
        "title_hint": {
            "en": "Kommo alternative for Georgia — EchoDesk vs Kommo",
            "ka": "Kommo-ს ალტერნატივა საქართველოში — EchoDesk vs Kommo",
        },
        "angle_hint": (
            "Target users actively searching 'Kommo ალტერნატივა'. Honest "
            "comparison: acknowledge Kommo's more mature WhatsApp template "
            "editor and global community. Lean into EchoDesk's GEL billing, "
            "Georgian hosting, bundled SIP calling + invoicing + booking + HR."
        ),
        "target_keywords": [
            "Kommo alternative", "Kommo ალტერნატივა",
            "CRM Georgia", "WhatsApp CRM Tbilisi",
        ],
    },
    {
        "slug": "bitrix24-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "ka",
        "competitor_name": "Bitrix24",
        "priority": 95,
        "title_hint": {
            "en": "Bitrix24 alternative for Georgian businesses — EchoDesk vs Bitrix24",
            "ka": "Bitrix24-ის ალტერნატივა ქართული ბიზნესებისთვის",
        },
        "angle_hint": (
            "Bitrix24 has a massive feature surface but is often overkill + "
            "bloated for Georgian SMBs. Concede Bitrix's deeper HR/project "
            "features for large teams. Lean into EchoDesk's lighter, pay-per-"
            "feature model and Georgian-first UX."
        ),
        "target_keywords": [
            "Bitrix24 alternative", "Bitrix24 ალტერნატივა",
            "CRM საქართველო", "helpdesk Tbilisi",
        ],
    },
    {
        "slug": "wati-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "WATI",
        "priority": 90,
        "title_hint": {
            "en": "WATI alternative — EchoDesk for WhatsApp + calls + email",
            "ka": "WATI-ის ალტერნატივა — EchoDesk WhatsApp-ისა და ზარებისთვის",
        },
        "angle_hint": (
            "WATI is WhatsApp-only. EchoDesk bundles WhatsApp with SIP calls, "
            "email, Messenger, Instagram, invoices, and bookings in one tool "
            "for the price of a WATI mid-tier. Acknowledge WATI's deeper "
            "WhatsApp-template automation."
        ),
        "target_keywords": [
            "WATI alternative", "WhatsApp helpdesk Georgia",
            "omnichannel CRM", "multi-channel support Tbilisi",
        ],
    },
    {
        "slug": "hubspot-service-hub-alternative-georgia",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "HubSpot Service Hub",
        "priority": 85,
        "title_hint": {
            "en": "HubSpot Service Hub alternative for Georgia — why EchoDesk",
            "ka": "HubSpot-ის ალტერნატივა საქართველოში",
        },
        "angle_hint": (
            "HubSpot is great for US/EU mid-market but eye-watering at scale "
            "and paid in USD. EchoDesk fits Georgian SMBs who want a modern "
            "CRM billed in GEL without committing to a multi-thousand-dollar "
            "HubSpot seat ladder. Concede HubSpot's superior marketing tools."
        ),
        "target_keywords": [
            "HubSpot alternative Georgia", "affordable CRM Georgia",
            "HubSpot Service Hub price", "CRM GEL billing",
        ],
    },
    {
        "slug": "zendesk-alternative-georgia",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "Zendesk",
        "priority": 80,
        "title_hint": {
            "en": "Zendesk alternative for Georgia — EchoDesk vs Zendesk",
            "ka": "Zendesk-ის ალტერნატივა",
        },
        "angle_hint": (
            "Zendesk is industry standard for helpdesk but priced per agent "
            "at premium rates, English-first UI, no local phone bundling. "
            "EchoDesk matches the ticketing core, adds SIP calling + "
            "invoicing + bookings, and ships Georgian localization."
        ),
        "target_keywords": [
            "Zendesk alternative", "helpdesk Georgia",
            "ticketing system Tbilisi", "CRM with phone",
        ],
    },
    {
        "slug": "intercom-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "Intercom",
        "priority": 75,
        "title_hint": {
            "en": "Intercom alternative for Georgian teams — EchoDesk comparison",
            "ka": "Intercom-ის ალტერნატივა",
        },
        "angle_hint": (
            "Intercom pioneered live chat but leans heavily on AI bots now "
            "and pricing scales aggressively. EchoDesk offers a unified "
            "inbox with transparent feature-based GEL pricing. Concede "
            "Intercom's stronger AI messaging + analytics."
        ),
        "target_keywords": [
            "Intercom alternative", "live chat Georgia",
            "unified inbox software", "customer messaging platform",
        ],
    },
    {
        "slug": "freshdesk-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "Freshdesk",
        "priority": 70,
        "title_hint": {
            "en": "Freshdesk alternative for Georgia — EchoDesk vs Freshdesk",
            "ka": "Freshdesk-ის ალტერნატივა",
        },
        "angle_hint": (
            "Freshdesk is a decent global helpdesk but lacks Georgian "
            "localization, SIP bundling, and GEL billing. Acknowledge "
            "Freshdesk's broader integrations marketplace."
        ),
        "target_keywords": [
            "Freshdesk alternative", "helpdesk Georgian language",
            "support software Tbilisi",
        ],
    },
    {
        "slug": "respond-io-vs-echodesk",
        "post_type": "comparison",
        "primary_language": "en",
        "competitor_name": "Respond.io",
        "priority": 65,
        "title_hint": {
            "en": "Respond.io alternative — EchoDesk for omnichannel messaging",
            "ka": "Respond.io-ს ალტერნატივა",
        },
        "angle_hint": (
            "Respond.io is messaging-focused but doesn't include phone + "
            "invoicing + bookings. Position EchoDesk as an all-in-one for "
            "businesses that need more than just channel aggregation."
        ),
        "target_keywords": [
            "Respond.io alternative", "omnichannel messaging Georgia",
        ],
    },

    # ------------------------------------------------------------------
    # How-to guides — long-tail informational.
    # ------------------------------------------------------------------
    {
        "slug": "how-to-set-up-whatsapp-business-api-georgia",
        "post_type": "how_to",
        "primary_language": "ka",
        "priority": 60,
        "title_hint": {
            "en": "How to set up WhatsApp Business API for your Georgian business",
            "ka": "როგორ დავაყენოთ WhatsApp Business API ქართული ბიზნესისთვის",
        },
        "angle_hint": (
            "Step-by-step walkthrough targeting small businesses just "
            "starting with WhatsApp for customer support. Cover: Meta "
            "Business Manager setup, phone verification, template approval "
            "basics, connecting to EchoDesk."
        ),
        "target_keywords": [
            "WhatsApp Business API Georgia", "WhatsApp Business setup",
            "WhatsApp დაყენება ბიზნესისთვის",
        ],
    },
    {
        "slug": "how-to-run-a-call-center-from-tbilisi",
        "post_type": "how_to",
        "primary_language": "ka",
        "priority": 55,
        "title_hint": {
            "en": "How to run a small call center from Tbilisi on a budget",
            "ka": "როგორ ავამუშავოთ პატარა ქოლ-ცენტრი თბილისიდან",
        },
        "angle_hint": (
            "Practical: SIP phone numbers in Georgia, IVR setup, recording "
            "compliance, team scheduling. Written for a solo founder or "
            "5-person team, not enterprise."
        ),
        "target_keywords": [
            "call center Tbilisi", "SIP phone Georgia",
            "ქოლ ცენტრი თბილისი", "IVR საქართველო",
        ],
    },
    {
        "slug": "how-to-invoice-in-gel-from-a-crm",
        "post_type": "how_to",
        "primary_language": "ka",
        "priority": 50,
        "title_hint": {
            "en": "How to issue invoices in GEL directly from your CRM",
            "ka": "როგორ გამოვწეროთ ინვოისი ლარში პირდაპირ CRM-დან",
        },
        "angle_hint": (
            "Walk through creating an invoice, attaching it to a customer "
            "ticket, sending via email, tracking payment. Touch on RS.ge "
            "compliance at a high level without giving tax advice."
        ),
        "target_keywords": [
            "invoice in GEL", "ინვოისი ლარში", "CRM invoicing Georgia",
        ],
    },
    {
        "slug": "how-to-manage-agent-leave-in-a-support-team",
        "post_type": "how_to",
        "primary_language": "ka",
        "priority": 45,
        "title_hint": {
            "en": "How to manage agent leave and shift handoffs in a support team",
            "ka": "როგორ მართოთ აგენტების შვებულება და ცვლები",
        },
        "angle_hint": (
            "Practical guide for a small support team: request flow, "
            "approval chain, shift coverage when someone's off, auto-"
            "reassignment of tickets, deadline impact."
        ),
        "target_keywords": [
            "agent leave management", "support team scheduling",
            "შვებულებების მართვა", "HR small team Georgia",
        ],
    },

    # ------------------------------------------------------------------
    # Use-case narratives — scenario-driven.
    # ------------------------------------------------------------------
    {
        "slug": "ecommerce-support-queue-georgia",
        "post_type": "use_case",
        "primary_language": "ka",
        "priority": 40,
        "title_hint": {
            "en": "Running an e-commerce support queue across WhatsApp, Instagram, and email",
            "ka": "ელექტრონული კომერციის მხარდაჭერა WhatsApp-ზე, Instagram-ზე და ელფოსტაზე",
        },
        "angle_hint": (
            "Concrete persona: a Georgian online fashion store with 3-5 "
            "staff handling customer orders, returns, and pre-sale "
            "questions. Walk through a day in the life using EchoDesk."
        ),
        "target_keywords": [
            "e-commerce support Georgia", "Instagram DM tool",
            "ელკომერცია მხარდაჭერა",
        ],
    },
    {
        "slug": "salon-bookings-crm-georgia",
        "post_type": "use_case",
        "primary_language": "ka",
        "priority": 35,
        "title_hint": {
            "en": "A salon's guide to managing bookings and client follow-ups in one tool",
            "ka": "სილამაზის სალონისთვის — ჯავშნები და კლიენტებთან კომუნიკაცია ერთ სისტემაში",
        },
        "angle_hint": (
            "Persona: a Tbilisi beauty salon with 5-10 staff, walk-ins + "
            "recurring clients, WhatsApp as primary channel. Show booking "
            "confirmations, reminders, post-visit follow-ups, loyalty "
            "tracking all in EchoDesk."
        ),
        "target_keywords": [
            "salon booking software Georgia", "სალონი ჯავშნები",
            "appointment system Tbilisi",
        ],
    },
    {
        "slug": "law-firm-helpdesk-invoicing-georgia",
        "post_type": "use_case",
        "primary_language": "ka",
        "priority": 30,
        "title_hint": {
            "en": "Call center, helpdesk, and invoicing for a Georgian law firm",
            "ka": "ქოლ-ცენტრი, ტიკეტინგი და ინვოისები ქართული იურიდიული ფირმისთვის",
        },
        "angle_hint": (
            "Persona: mid-size Tbilisi law office, 10-15 lawyers + 3 support "
            "staff. Show intake via phone + email, matter tracking via "
            "tickets, GEL invoicing, and leave management all in EchoDesk."
        ),
        "target_keywords": [
            "law firm software Georgia", "იურიდიული ფირმა CRM",
            "legal practice management Tbilisi",
        ],
    },
]


def seed_topics(apps, schema_editor):
    BlogTopic = apps.get_model("blog", "BlogTopic")
    for item in SEED_TOPICS:
        BlogTopic.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "post_type": item["post_type"],
                "primary_language": item.get("primary_language", "ka"),
                "competitor_name": item.get("competitor_name", ""),
                "priority": item["priority"],
                "title_hint": item["title_hint"],
                "angle_hint": item["angle_hint"],
                "target_keywords": item["target_keywords"],
                "status": "pending",
            },
        )


def unseed_topics(apps, schema_editor):
    BlogTopic = apps.get_model("blog", "BlogTopic")
    slugs = [item["slug"] for item in SEED_TOPICS]
    BlogTopic.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("blog", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_topics, reverse_code=unseed_topics),
    ]
