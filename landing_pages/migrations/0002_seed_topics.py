"""Seed the initial LandingTopic queue.

Drops a hand-curated list of 16 topics so the AI pipeline has a 2-week
runway before admin needs more. Admins can add more through the Django
admin at any time.

Categories:
- 8 feature deep-dives (high-intent long-tail queries: WhatsApp API, SIP, GEL invoicing, etc.)
- 4 vertical pages (Georgian industry positioning)
- 4 competitor comparisons (bottom-of-funnel traffic)

Priorities are set so the most competitive-intent content drafts first.
"""

from django.db import migrations


SEED_TOPICS = [
    # ------------------------------------------------------------------
    # Feature deep-dives — priority 100 → 70.
    # ------------------------------------------------------------------
    {
        "slug": "whatsapp-business-crm-georgia",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 100,
        "highlighted_feature_slugs": ["whatsapp", "templates"],
        "title_hint": {
            "en": "WhatsApp Business CRM for Georgia",
            "ka": "WhatsApp Business CRM საქართველოში",
        },
        "angle_hint": (
            "Target: Georgian SMBs who want WhatsApp Business API access "
            "without Meta-verification headaches. Lead with the fact that "
            "EchoDesk ships the Cloud API connection + approved templates "
            "+ unified inbox with Messenger / Instagram / email / calls. "
            "Differentiators: GEL billing (no USD conversion), 80 msg/s "
            "throughput, native Georgian templates. Honest about the "
            "limitation: still requires a Meta Business account."
        ),
        "target_keywords": [
            "WhatsApp Business API საქართველო",
            "whatsapp business api georgia",
            "WhatsApp CRM Tbilisi",
            "ვაცაპ ბიზნესი",
            "WhatsApp Cloud API Georgia",
        ],
    },
    {
        "slug": "call-center-software-tbilisi",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 95,
        "highlighted_feature_slugs": ["sip", "pbx", "recording"],
        "title_hint": {
            "en": "Call center software in Tbilisi",
            "ka": "ქოლ-ცენტრის პროგრამა თბილისში",
        },
        "angle_hint": (
            "Target: Georgian SMBs wanting a call center without rebuilding "
            "from scratch — Asterisk 20 + SIP queues (rrmemory) + MixMonitor "
            "recording + voicemail + per-user extensions. Georgian SIP trunk "
            "(89.150.1.11) is pre-configured. Wedge: call center bundled with "
            "tickets / invoicing / CRM in one GEL-billed platform, no need "
            "for a separate PBX provider."
        ),
        "target_keywords": [
            "SIP call center Tbilisi",
            "ქოლ ცენტრი თბილისი",
            "call center software georgia",
            "Asterisk Georgia",
            "SIP trunk Tbilisi",
        ],
    },
    {
        "slug": "invoice-software-gel",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 90,
        "highlighted_feature_slugs": ["invoicing", "bog", "recurring"],
        "title_hint": {
            "en": "Invoice software in GEL",
            "ka": "ინვოისის პროგრამა ლარში",
        },
        "angle_hint": (
            "Target: Georgian SMBs that need to issue invoices in GEL without "
            "converting from USD. Lead with Draft → Sent → Viewed → Paid "
            "states, recurring invoices with saved-card retry, Bank of "
            "Georgia OAuth2 integration, IBAN / SWIFT fields built in. "
            "Concrete wedge: no other CRM bundles GEL invoicing + BOG "
            "payments + recurring billing at this price point."
        ),
        "target_keywords": [
            "invoice software GEL",
            "ინვოისი ლარში",
            "ინვოისის პროგრამა",
            "Bank of Georgia CRM",
            "recurring invoices Georgia",
        ],
    },
    {
        "slug": "booking-software-georgia",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 85,
        "highlighted_feature_slugs": ["bookings", "calendar"],
        "title_hint": {
            "en": "Booking software for Georgia",
            "ka": "ჯავშნის სისტემა საქართველოში",
        },
        "angle_hint": (
            "Target: Georgian service businesses (salons, clinics, consultants) "
            "needing a calendar + online booking. Lead with multilingual "
            "booking forms (ka / ru / en), per-service slots, payments per "
            "booking. Wedge: booking comes bundled with WhatsApp / email "
            "customer comms + GEL invoicing — no Zapier, no separate tool."
        ),
        "target_keywords": [
            "booking software Georgia",
            "ჯავშნის სისტემა",
            "appointment system Tbilisi",
            "online booking Georgia",
            "სერვისის ჯავშანი",
        ],
    },
    {
        "slug": "email-helpdesk-georgia",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 80,
        "highlighted_feature_slugs": ["email", "tickets"],
        "title_hint": {
            "en": "Email helpdesk for Georgia",
            "ka": "ელფოსტის Helpdesk საქართველოსთვის",
        },
        "angle_hint": (
            "Target: Georgian support teams drowning in shared mailboxes. "
            "IMAP / SMTP two-way sync, thread grouping, seen / flagged / "
            "labeled states, multi-connection, full Georgian font support. "
            "Wedge: email becomes first-class tickets (Kanban + tags + "
            "priorities) instead of living in a siloed inbox. No separate "
            "ticketing SaaS needed."
        ),
        "target_keywords": [
            "email helpdesk Georgia",
            "ელფოსტის მხარდაჭერა",
            "shared mailbox CRM",
            "Gmail helpdesk Georgia",
            "ქართული helpdesk",
        ],
    },
    {
        "slug": "ticket-management-georgia",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 75,
        "highlighted_feature_slugs": ["tickets", "kanban"],
        "title_hint": {
            "en": "Ticket management for Georgia",
            "ka": "ბილეთების მართვა",
        },
        "angle_hint": (
            "Target: Georgian SMBs that need Kanban-style ticket tracking "
            "with tags, priorities, and assignment. Lead with per-ticket "
            "payment tracking — unique for a helpdesk in this price band. "
            "Wedge: tickets auto-created from WhatsApp / Messenger / "
            "Instagram / email / calls, all in one queue. GEL billing."
        ),
        "target_keywords": [
            "ticket management Georgia",
            "ბილეთების სისტემა",
            "helpdesk Georgia",
            "kanban support Tbilisi",
            "customer support software Georgia",
        ],
    },
    {
        "slug": "leave-management-georgia",
        "page_type": "feature",
        "primary_language": "ka",
        "priority": 73,
        "highlighted_feature_slugs": ["leave"],
        "title_hint": {
            "en": "Leave management for Georgia",
            "ka": "შვებულების მართვა",
        },
        "angle_hint": (
            "Target: Georgian SMBs tired of tracking leave in spreadsheets. "
            "Types (Vacation / Sick / Personal), manager + optional HR "
            "approval workflow, accrual vs annual balance, Georgian "
            "labor-calendar holidays built in. Wedge: HR module is bundled "
            "with the rest of EchoDesk at feature pricing — no separate HR "
            "SaaS subscription."
        ),
        "target_keywords": [
            "leave management Georgia",
            "შვებულების მართვა",
            "HR software Georgia",
            "Georgian labor calendar",
            "employee leave Tbilisi",
        ],
    },
    {
        "slug": "tiktok-shop-crm-georgia",
        "page_type": "feature",
        "primary_language": "en",
        "priority": 70,
        "highlighted_feature_slugs": ["tiktok", "tickets"],
        "title_hint": {
            "en": "TikTok Shop CRM for Georgia",
            "ka": "TikTok Shop CRM",
        },
        "angle_hint": (
            "Target: Georgian e-commerce sellers running TikTok Shop as a "
            "channel. Two-way DMs with buyers, messages auto-become "
            "tickets, unified with WhatsApp / Instagram / email. Wedge: "
            "one of very few CRMs with native TikTok Shop integration, "
            "and the only one billed in GEL."
        ),
        "target_keywords": [
            "TikTok Shop CRM",
            "TikTok Shop Georgia",
            "TikTok seller tools",
            "TikTok DM management",
            "e-commerce Tbilisi",
        ],
    },

    # ------------------------------------------------------------------
    # Vertical pages — priority 65 → 60.
    # ------------------------------------------------------------------
    {
        "slug": "for-salons",
        "page_type": "vertical",
        "primary_language": "ka",
        "priority": 65,
        "highlighted_feature_slugs": ["bookings", "whatsapp", "invoicing"],
        "title_hint": {
            "en": "EchoDesk for salons",
            "ka": "EchoDesk სილამაზის სალონებისთვის",
        },
        "angle_hint": (
            "Target: Tbilisi beauty salons (5-10 staff), booking-driven. "
            "Walk-ins + recurring clients, WhatsApp as primary channel. "
            "Lead with bookings + reminders + post-visit follow-ups, GEL "
            "invoicing for packages / memberships. Wedge: one tool instead "
            "of separate booking app + WhatsApp manager + invoicing "
            "software."
        ),
        "target_keywords": [
            "salon booking software Georgia",
            "სალონი CRM",
            "beauty salon Tbilisi software",
            "სალონი ჯავშნები",
            "spa management Georgia",
        ],
    },
    {
        "slug": "for-law-firms",
        "page_type": "vertical",
        "primary_language": "ka",
        "priority": 63,
        "highlighted_feature_slugs": ["tickets", "invoicing", "email", "recording"],
        "title_hint": {
            "en": "EchoDesk for law firms",
            "ka": "EchoDesk იურიდიული ფირმებისთვის",
        },
        "angle_hint": (
            "Target: mid-size Tbilisi law firms (10-15 lawyers + 3 support "
            "staff). Matter intake via phone + email, tracking via tickets, "
            "call recording for evidentiary purposes, GEL invoicing for "
            "billable hours. Wedge: call recording + matter tickets + "
            "invoicing together — compliance-friendly for Georgian legal "
            "practice."
        ),
        "target_keywords": [
            "law firm software Georgia",
            "იურიდიული ფირმა CRM",
            "legal practice management Tbilisi",
            "call recording law firm Georgia",
            "ადვოკატი პროგრამა",
        ],
    },
    {
        "slug": "for-ecommerce",
        "page_type": "vertical",
        "primary_language": "ka",
        "priority": 62,
        "highlighted_feature_slugs": ["whatsapp", "tiktok", "tickets", "invoicing"],
        "title_hint": {
            "en": "EchoDesk for e-commerce",
            "ka": "EchoDesk ელ-კომერციისთვის",
        },
        "angle_hint": (
            "Target: Georgian online stores (3-10 staff) running WhatsApp + "
            "Instagram + TikTok Shop + email. Unified inbox, messages → "
            "tickets, GEL invoicing + BOG payments. Wedge: no other "
            "omnichannel CRM bundles TikTok Shop + GEL invoicing + BOG at "
            "this price. Honest: we don't replace your storefront."
        ),
        "target_keywords": [
            "e-commerce CRM Georgia",
            "ელ კომერცია მხარდაჭერა",
            "omnichannel support Georgia",
            "Instagram DM tool Tbilisi",
            "Shopify Georgia alternative",
        ],
    },
    {
        "slug": "for-clinics",
        "page_type": "vertical",
        "primary_language": "ka",
        "priority": 60,
        "highlighted_feature_slugs": ["bookings", "whatsapp", "sip"],
        "title_hint": {
            "en": "EchoDesk for clinics",
            "ka": "EchoDesk კლინიკებისთვის",
        },
        "angle_hint": (
            "Target: small / mid Georgian clinics and private practices. "
            "Patient bookings + SIP receptionist queue + WhatsApp reminders. "
            "Lead with appointment management + call routing to available "
            "staff + Georgian-language forms. Wedge: no need for a clinic-"
            "specific SaaS; this is general enough to fit but bundles the "
            "right parts."
        ),
        "target_keywords": [
            "clinic booking software Georgia",
            "კლინიკა CRM",
            "medical appointments Tbilisi",
            "clinic phone system Georgia",
            "appointment reminder Georgia",
        ],
    },

    # ------------------------------------------------------------------
    # Comparison pages — priority 55 → 40.
    # ------------------------------------------------------------------
    {
        "slug": "compare-kommo",
        "page_type": "comparison",
        "primary_language": "ka",
        "competitor_name": "Kommo",
        "priority": 55,
        "highlighted_feature_slugs": ["whatsapp", "invoicing", "sip"],
        "title_hint": {
            "en": "EchoDesk vs Kommo",
            "ka": "EchoDesk vs Kommo — შედარება",
        },
        "angle_hint": (
            "Honest comparison. Concede Kommo's more mature WhatsApp "
            "template editor and larger global community. Lean EchoDesk "
            "wins into GEL billing (no USD conversion), Georgian hosting, "
            "bundled SIP + invoicing + bookings + HR, feature-based "
            "pricing. Do NOT invent Kommo prices."
        ),
        "target_keywords": [
            "Kommo alternative Georgia",
            "Kommo ალტერნატივა",
            "CRM comparison Tbilisi",
            "WhatsApp CRM comparison",
            "EchoDesk vs Kommo",
        ],
    },
    {
        "slug": "compare-bitrix24",
        "page_type": "comparison",
        "primary_language": "ka",
        "competitor_name": "Bitrix24",
        "priority": 50,
        "highlighted_feature_slugs": ["whatsapp", "invoicing", "sip", "bookings"],
        "title_hint": {
            "en": "EchoDesk vs Bitrix24",
            "ka": "EchoDesk vs Bitrix24",
        },
        "angle_hint": (
            "Honest comparison. Concede Bitrix24's deeper HR / project "
            "management features for large teams. Lean EchoDesk wins into "
            "lighter pay-per-feature pricing, Georgian-first UX, "
            "Georgia-hosted data, bundled SIP calling out of the box. Do "
            "NOT invent Bitrix24 feature lists or prices."
        ),
        "target_keywords": [
            "Bitrix24 alternative Georgia",
            "Bitrix24 ალტერნატივა",
            "CRM comparison Georgia",
            "Bitrix24 vs EchoDesk",
            "lightweight CRM Georgia",
        ],
    },
    {
        "slug": "compare-wati",
        "page_type": "comparison",
        "primary_language": "en",
        "competitor_name": "WATI",
        "priority": 45,
        "highlighted_feature_slugs": ["whatsapp", "sip", "invoicing", "bookings"],
        "title_hint": {
            "en": "EchoDesk vs WATI",
            "ka": "EchoDesk vs WATI",
        },
        "angle_hint": (
            "WATI is WhatsApp-only. EchoDesk bundles WhatsApp with SIP "
            "calls, email, Messenger, Instagram, invoices, and bookings "
            "for Georgian SMBs. Concede WATI's deeper WhatsApp-template "
            "automation. Lean into the 'one tool instead of five' wedge. "
            "Do NOT invent WATI prices or feature gaps."
        ),
        "target_keywords": [
            "WATI alternative",
            "WhatsApp helpdesk Georgia",
            "WATI vs EchoDesk",
            "omnichannel vs WhatsApp-only",
            "WATI alternative Georgia",
        ],
    },
    {
        "slug": "compare-zendesk",
        "page_type": "comparison",
        "primary_language": "en",
        "competitor_name": "Zendesk",
        "priority": 40,
        "highlighted_feature_slugs": ["tickets", "sip", "invoicing", "whatsapp"],
        "title_hint": {
            "en": "EchoDesk vs Zendesk",
            "ka": "EchoDesk vs Zendesk",
        },
        "angle_hint": (
            "Zendesk is the helpdesk industry standard but priced per "
            "agent at premium rates, English-first, no Georgian SIP "
            "bundling. EchoDesk matches the ticketing core, adds SIP + "
            "invoicing + bookings, ships Georgian UI, billed in GEL. "
            "Concede Zendesk's larger app marketplace and macro-based "
            "automation. Do NOT invent Zendesk prices or feature details."
        ),
        "target_keywords": [
            "Zendesk alternative Georgia",
            "Zendesk ალტერნატივა",
            "helpdesk Georgia comparison",
            "Zendesk vs EchoDesk",
            "affordable helpdesk Tbilisi",
        ],
    },
]


def seed_topics(apps, schema_editor):
    LandingTopic = apps.get_model("landing_pages", "LandingTopic")
    for item in SEED_TOPICS:
        LandingTopic.objects.update_or_create(
            slug=item["slug"],
            defaults={
                "page_type": item["page_type"],
                "primary_language": item.get("primary_language", "ka"),
                "competitor_name": item.get("competitor_name", ""),
                "priority": item["priority"],
                "title_hint": item["title_hint"],
                "angle_hint": item["angle_hint"],
                "target_keywords": item["target_keywords"],
                "highlighted_feature_slugs": item.get("highlighted_feature_slugs", []),
                "status": "pending",
            },
        )


def unseed_topics(apps, schema_editor):
    LandingTopic = apps.get_model("landing_pages", "LandingTopic")
    slugs = [item["slug"] for item in SEED_TOPICS]
    LandingTopic.objects.filter(slug__in=slugs).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("landing_pages", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_topics, reverse_code=unseed_topics),
    ]
