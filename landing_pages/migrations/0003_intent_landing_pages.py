"""Seed three intent-based SEO landing pages.

The marketing-page library so far covered competitor comparisons,
verticals, and a handful of broad features. Three high-intent Georgian
queries weren't directly addressed:

  * "WhatsApp helpdesk Georgia" — buyers explicitly looking for an
    inbox-style WhatsApp tool, not a CRM that happens to integrate.
  * "GEL invoicing software" — buyers who want lari-priced invoicing
    glued to BOG/TBC payment links.
  * "SIP PBX CRM Georgia" — buyers replacing a desk phone setup who
    also need ticketing/messaging in the same tool.

Each gets its own slug + content_blocks (benefit_grid + checklist) +
FAQ. Frontend renders via the existing src/app/[slug]/page.tsx route
and the LandingPageView component.
"""
from django.db import migrations
from django.utils import timezone


# ----------------------------------------------------------------------------
# Page 1: WhatsApp helpdesk Georgia
# ----------------------------------------------------------------------------

WHATSAPP_PAGE = {
    "slug": "whatsapp-helpdesk-georgia",
    "page_type": "feature",
    "title": {
        "en": "WhatsApp helpdesk for Georgian SMBs",
        "ka": "WhatsApp helpdesk ქართული ბიზნესისთვის",
    },
    "hero_subtitle": {
        "en": "Stop juggling phones and personal accounts. Route every WhatsApp Business message to the right agent, see history per customer, and reply 3x faster.",
        "ka": "შეწყვიტე პირადი WhatsApp-ით პასუხის გაცემა. გადაანაწილე ყველა WhatsApp Business შეტყობინება სწორ ოპერატორზე, ნახე საუბრების ისტორია კლიენტზე და უპასუხე 3-ჯერ უფრო სწრაფად.",
    },
    "summary": {
        "en": "EchoDesk turns WhatsApp Business into a multi-agent helpdesk: one inbox, assignment rules, internal notes, customer cards, and reporting — billed in GEL.",
        "ka": "EchoDesk WhatsApp Business-ს აქცევს მრავალოპერატორულ helpdesk-ად: ერთი ინბოქსი, მინიჭების წესები, შიდა შენიშვნები, კლიენტის ბარათები და რეპორტინგი — ლარში.",
    },
    "meta_title": {
        "en": "WhatsApp Helpdesk Georgia — Multi-Agent Inbox in GEL | EchoDesk",
        "ka": "WhatsApp Helpdesk საქართველოში — მრავალოპერატორული ინბოქსი | EchoDesk",
    },
    "meta_description": {
        "en": "Run a real WhatsApp helpdesk from Georgia: assign chats, see customer history, reply faster. WhatsApp Business API, GEL pricing, Tbilisi-based support.",
        "ka": "WhatsApp helpdesk ქართულად: ჩატების მინიჭება, კლიენტის ისტორია, სწრაფი პასუხები. WhatsApp Business API, ლარში ფასები, თბილისიდან მხარდაჭერა.",
    },
    "keywords": [
        "WhatsApp helpdesk Georgia",
        "WhatsApp Business CRM Tbilisi",
        "ვოთსაფი ბიზნესი helpdesk",
        "multi-agent WhatsApp inbox",
        "WhatsApp customer support GEL",
    ],
    "og_tag": "WhatsApp",
    "highlighted_feature_slugs": ["whatsapp_business", "ticket_management", "auto_reply"],
    "content_blocks": [
        {
            "type": "benefit_grid",
            "heading_en": "Why teams switch from a personal phone",
            "heading_ka": "რატომ ცვლიან გუნდები პირად ტელეფონს EchoDesk-ით",
            "items": [
                {
                    "icon": "users",
                    "title_en": "Multiple agents on one number",
                    "title_ka": "ერთი ნომერი — რამდენიმე ოპერატორი",
                    "description_en": "Up to 12 agents share the same WhatsApp Business number with conflict-free assignment.",
                    "description_ka": "12-მდე ოპერატორი იზიარებს ერთ WhatsApp Business ნომერს, კონფლიქტის გარეშე ხდება ჩატების მინიჭება.",
                },
                {
                    "icon": "clock",
                    "title_en": "Reply 3× faster",
                    "title_ka": "3-ჯერ უფრო სწრაფი პასუხი",
                    "description_en": "Saved replies, auto-routing by working hours, and SLA timers cut average first-response below 90 seconds.",
                    "description_ka": "ნიმუშოვანი პასუხები, სამუშაო საათების მიხედვით ავტომატური მარშრუტიზაცია და SLA ტაიმერები ამცირებენ პასუხის დროს 90 წამამდე.",
                },
                {
                    "icon": "history",
                    "title_en": "Full customer history",
                    "title_ka": "სრული კლიენტის ისტორია",
                    "description_en": "Every chat ties to a customer card with past tickets, calls, invoices, and notes — no scrolling through thousands of personal messages.",
                    "description_ka": "ყველა საუბარი კლიენტის ბარათს უკავშირდება — წარსული ტიკეტები, ზარები, ინვოისები, შენიშვნები ერთ ადგილას.",
                },
                {
                    "icon": "bar-chart-3",
                    "title_en": "Real reporting",
                    "title_ka": "რეალური სტატისტიკა",
                    "description_en": "Per-agent volume, SLA breach rate, customer satisfaction — exportable per channel.",
                    "description_ka": "ოპერატორის მოცულობა, SLA-ის დარღვევები, კლიენტთა შეფასება — ექსპორტირდება არხის მიხედვით.",
                },
            ],
        },
        {
            "type": "checklist",
            "heading_en": "What you get on day one",
            "heading_ka": "რას იღებთ პირველი დღიდან",
            "items": [
                {"text_en": "Official WhatsApp Business API connection (no banned-account risk).", "text_ka": "WhatsApp Business API ოფიციალური კავშირი — ანგარიშის ბლოკის რისკის გარეშე."},
                {"text_en": "Round-robin or skill-based assignment.", "text_ka": "რიგრიგობით ან კომპეტენციის მიხედვით ჩატების განაწილება."},
                {"text_en": "Welcome + away auto-replies, per channel.", "text_ka": "სალამის და არასამუშაო საათების ავტომატური პასუხები, არხის მიხედვით."},
                {"text_en": "Internal notes invisible to the customer.", "text_ka": "შიდა შენიშვნები, რომლებიც კლიენტს არ უჩანს."},
                {"text_en": "Bulk export: contacts, conversations, attachments.", "text_ka": "ექსპორტი: კონტაქტები, საუბრები, დანართები."},
                {"text_en": "Tbilisi-based support in Georgian or English.", "text_ka": "მხარდაჭერა თბილისიდან ქართულად ან ინგლისურად."},
            ],
        },
    ],
    "faq_items": [
        {
            "question_en": "Do I keep my existing WhatsApp Business number?",
            "question_ka": "ჩემი არსებული WhatsApp Business ნომერი დარჩება?",
            "answer_en": "Yes. We connect via the official Business API — your number stays with you and existing contacts keep their conversation history.",
            "answer_ka": "კი. ჩვენ ვუკავშირდებით ოფიციალური Business API-ით — ნომერი თქვენი რჩება და კლიენტებთან საუბრის ისტორია უცვლელად ნარჩუნდება.",
        },
        {
            "question_en": "How long does setup take?",
            "question_ka": "რამდენი დრო სჭირდება ინსტალაციას?",
            "answer_en": "About 30 minutes if your WhatsApp Business account is already verified. Otherwise verification takes 1–3 business days through Meta — we walk you through it.",
            "answer_ka": "დაახლოებით 30 წუთი, თუ თქვენი WhatsApp Business ანგარიში უკვე ვერიფიცირებულია. წინააღმდეგ შემთხვევაში Meta-ს ვერიფიკაცია 1–3 სამუშაო დღე გრძელდება — გავცემთ ინსტრუქციას.",
        },
        {
            "question_en": "Is it billed in GEL?",
            "question_ka": "ფასები ლარშია?",
            "answer_en": "Yes. Monthly subscription is in GEL. WhatsApp's per-conversation fees are passed through at Meta's published rates with no markup.",
            "answer_ka": "კი. ყოველთვიური გამოწერა ლარშია. WhatsApp-ის საუბრის გადასახადები Meta-ს ოფიციალური ფასებით გადადის, დანამატის გარეშე.",
        },
    ],
}


# ----------------------------------------------------------------------------
# Page 2: GEL invoicing software
# ----------------------------------------------------------------------------

INVOICING_PAGE = {
    "slug": "gel-invoicing-software",
    "page_type": "feature",
    "title": {
        "en": "GEL invoicing software for Georgian businesses",
        "ka": "ლარში ინვოისების პროგრამა ქართული ბიზნესისთვის",
    },
    "hero_subtitle": {
        "en": "Issue lari invoices, attach BOG or TBC payment links, and reconcile in your Georgian bank — all from the same tool that runs your inbox and PBX.",
        "ka": "გამოუშვი ლარში ინვოისები, ჩასვი BOG-ისა ან TBC-ის გადახდის ბმულები და დაუკავშირე ქართულ ბანკს — იმავე სისტემიდან, საიდანაც გამყავთ ინბოქსი და PBX.",
    },
    "summary": {
        "en": "EchoDesk's invoicing module is built around the Georgian banking stack: BOG e-Commerce, TBC Pay, and bank-statement reconciliation, with VAT-ready PDFs in two languages.",
        "ka": "EchoDesk-ის ინვოისების მოდული აგებულია ქართული ბანკების ეკოსისტემაზე: BOG e-Commerce, TBC Pay, საბანკო ამონაწერის დასუფთავება, დღგ-სთვის მზა PDF-ები ორ ენაზე.",
    },
    "meta_title": {
        "en": "GEL Invoicing Software — BOG + TBC Payment Links | EchoDesk",
        "ka": "ლარში ინვოისების პროგრამა — BOG + TBC | EchoDesk",
    },
    "meta_description": {
        "en": "Invoice in GEL, attach BOG or TBC payment links, and reconcile automatically. Built for Georgian SMBs — VAT-ready PDFs, bilingual, no USD conversion fees.",
        "ka": "ლარში ინვოისები, BOG-ისა და TBC-ის გადახდის ბმულებით, ავტომატური დასუფთავება. ქართული ბიზნესისთვის — დღგ-სთვის მზა PDF-ები, ორენოვანი, USD-ში კონვერტაციის გარეშე.",
    },
    "keywords": [
        "GEL invoicing software",
        "ლარში ინვოისები",
        "BOG payment integration",
        "TBC Pay invoice",
        "Georgia VAT invoice software",
        "BOG e-Commerce CRM",
    ],
    "og_tag": "Invoicing",
    "highlighted_feature_slugs": ["invoicing", "subscription_billing"],
    "content_blocks": [
        {
            "type": "benefit_grid",
            "heading_en": "Built for Georgian banking, not localised from English",
            "heading_ka": "შექმნილია ქართული ბანკებისთვის — არა გადათარგმნილი",
            "items": [
                {
                    "icon": "credit-card",
                    "title_en": "BOG + TBC payment links built in",
                    "title_ka": "BOG-ისა და TBC-ის გადახდის ბმულები ჩაშენებულია",
                    "description_en": "Generate a one-tap payment URL per invoice. Customers pay in lari via Apple Pay, Google Pay, or any GE-issued card.",
                    "description_ka": "ერთი ღილაკით გადახდის URL ყოველ ინვოისზე. კლიენტები იხდიან ლარში Apple Pay-ით, Google Pay-ით ან ნებისმიერი ქართული ბარათით.",
                },
                {
                    "icon": "file-text",
                    "title_en": "Bilingual VAT-ready PDFs",
                    "title_ka": "დღგ-სთვის მზა PDF — ორ ენაზე",
                    "description_en": "Auto-rendered Georgian + English invoice PDF, VAT line included, ready for the customer's accountant.",
                    "description_ka": "ავტომატური ქართულ-ინგლისური ინვოისის PDF, დღგ-ს ხაზით, კლიენტის ბუღალტრისთვის მზა.",
                },
                {
                    "icon": "refresh-cw",
                    "title_en": "Auto-reconciliation",
                    "title_ka": "ავტომატური დასუფთავება",
                    "description_en": "Pull statements from BOG and TBC, match payments to invoices by reference number, mark as paid without spreadsheet juggling.",
                    "description_ka": "BOG-დან და TBC-დან ამონაწერი ავტომატურად ხდება — გადახდები რეფერენს ნომრით ემთხვევა ინვოისებს, საფასო გადახდის ცხრილების გარეშე.",
                },
                {
                    "icon": "users-round",
                    "title_en": "Linked to your CRM",
                    "title_ka": "დაკავშირებული თქვენს CRM-თან",
                    "description_en": "Every invoice ties to a contact card with their tickets, calls, and chats — see open balances next to the conversation.",
                    "description_ka": "ყველა ინვოისი დაკავშირებულია კონტაქტის ბარათთან — დავალიანებები გვერდიგვერდ თქვენი საუბრის ისტორიასთან.",
                },
            ],
        },
        {
            "type": "checklist",
            "heading_en": "What you can issue today",
            "heading_ka": "რას გამოუშვებთ დღესვე",
            "items": [
                {"text_en": "One-off invoices with BOG / TBC payment links.", "text_ka": "ერთჯერადი ინვოისები BOG / TBC გადახდის ბმულებით."},
                {"text_en": "Recurring invoices (weekly / monthly / yearly cadences).", "text_ka": "განმეორებითი ინვოისები (კვირაში / თვეში / წელიწადში ერთხელ)."},
                {"text_en": "Subscription billing tied to feature usage in EchoDesk.", "text_ka": "გამოწერების ბილინგი, რომელიც EchoDesk-ის ფუნქციების გამოყენებას უკავშირდება."},
                {"text_en": "Late-payment reminders via SMS, email, or WhatsApp.", "text_ka": "გადახდის შეხსენებები SMS-ით, ელფოსტით ან WhatsApp-ით."},
                {"text_en": "Ledger view: paid vs outstanding, per customer + per period.", "text_ka": "ფინანსური ხედი: გადახდილი / გადასახდელი, კლიენტისა და პერიოდის მიხედვით."},
            ],
        },
    ],
    "faq_items": [
        {
            "question_en": "Do I need separate BOG and TBC merchant accounts?",
            "question_ka": "ცალკე მჭირდება BOG-ისა და TBC-ის მერჩანტ ანგარიშები?",
            "answer_en": "You need merchant accounts with whichever provider(s) you want to use — BOG e-Commerce, TBC Pay, or both. EchoDesk plugs into them once you have credentials.",
            "answer_ka": "გჭირდებათ მერჩანტ ანგარიში თქვენთვის სასურველ პროვაიდერთან (BOG e-Commerce, TBC Pay ან ორივე). EchoDesk იმდენად ერთვება, რამდენადაც კრედენშელები გაქვთ.",
        },
        {
            "question_en": "Is e-invoicing compliant with rs.ge requirements?",
            "question_ka": "ექვემდებარება rs.ge-ს მოთხოვნებს?",
            "answer_en": "Our PDFs include the line items, VAT, and seller/buyer details rs.ge expects. We don't auto-submit to rs.ge today — your accountant uploads them as usual. Native rs.ge submission is on the roadmap.",
            "answer_ka": "ჩვენი PDF-ები შეიცავს rs.ge-სთვის სავალდებულო ელემენტებს — ხაზებს, დღგ-ს, გამყიდველი/მყიდველი დეტალებს. ავტომატური ატვირთვა rs.ge-ში დღეს არ ხდება — ბუღალტერი თვითონ ატვირთავს. ეს ფუნქცია ჩვენ გეგმაშია.",
        },
    ],
}


# ----------------------------------------------------------------------------
# Page 3: SIP PBX CRM Georgia
# ----------------------------------------------------------------------------

PBX_PAGE = {
    "slug": "sip-pbx-crm-georgia",
    "page_type": "feature",
    "title": {
        "en": "SIP PBX + CRM for Georgian teams",
        "ka": "SIP PBX + CRM ქართული გუნდებისთვის",
    },
    "hero_subtitle": {
        "en": "Replace your desk-phone setup with a browser softphone tied to a real CRM. Bring your own Asterisk or use ours — Georgian DID, GEL pricing, recording included.",
        "ka": "შეცვალე ფიქსირებული ტელეფონები ბრაუზერის softphone-ით, რომელიც CRM-ს უკავშირდება. მოიტანე საკუთარი Asterisk ან ისარგებლე ჩვენით — ქართული DID, ლარში ფასი, ჩაწერა შედის.",
    },
    "summary": {
        "en": "EchoDesk gives you a per-agent extension, a queue, working-hours routing, call recording, and a 1-click softphone in the browser — all wired to the same customer cards your inbox sees.",
        "ka": "EchoDesk აძლევს ოპერატორს ხაზს, რიგს, სამუშაო საათების მარშრუტიზაციას, ზარის ჩაწერას და ბრაუზერის softphone-ს — ყველა დაკავშირებულია იმავე კლიენტთა ბარათებთან, რომლებსაც ხედავს თქვენი ინბოქსი.",
    },
    "meta_title": {
        "en": "SIP PBX + CRM Georgia — Browser Softphone, GEL Pricing | EchoDesk",
        "ka": "SIP PBX + CRM საქართველოში — ბრაუზერის softphone | EchoDesk",
    },
    "meta_description": {
        "en": "Run an Asterisk-backed PBX from your browser: queues, recordings, working-hours routing, customer history per call. Bring-your-own Asterisk supported, GEL billing, Tbilisi support.",
        "ka": "Asterisk-ზე დაფუძნებული PBX ბრაუზერიდან: რიგები, ჩაწერა, სამუშაო საათების მარშრუტიზაცია, ზარის ისტორია. საკუთარი Asterisk-ის გამოყენება შესაძლებელია, ლარში ფასი, თბილისიდან მხარდაჭერა.",
    },
    "keywords": [
        "SIP PBX CRM Georgia",
        "Asterisk CRM Tbilisi",
        "browser softphone Georgia",
        "Georgian DID call center",
        "ვირტუალური სატელეფონო ცენტრი",
        "WebRTC PBX Georgia",
    ],
    "og_tag": "PBX",
    "highlighted_feature_slugs": ["ip_calling", "call_recording"],
    "content_blocks": [
        {
            "type": "benefit_grid",
            "heading_en": "A real PBX without the old hardware",
            "heading_ka": "ნამდვილი PBX — ძველი ტექნიკის გარეშე",
            "items": [
                {
                    "icon": "phone-incoming",
                    "title_en": "Browser softphone, no installs",
                    "title_ka": "Softphone ბრაუზერიდან — ინსტალაცია არ სჭირდება",
                    "description_en": "Agents pick up calls from the same dashboard they answer chats. WSS-secured WebRTC, works on Chrome, Firefox, Safari.",
                    "description_ka": "ოპერატორები ზარებს იღებენ იმავე dashboard-დან, საიდანაც პასუხობენ ჩატებს. WSS-ით დაცული WebRTC, მუშაობს Chrome-ში, Firefox-ში, Safari-ში.",
                },
                {
                    "icon": "list-ordered",
                    "title_en": "Queues + working-hours routing",
                    "title_ka": "რიგები + სამუშაო საათები",
                    "description_en": "Round-robin or skill-based, with after-hours voicemail or callback. Full per-tenant control from the dashboard — no SSH.",
                    "description_ka": "რიგრიგობით ან კომპეტენციის მიხედვით, არასამუშაო საათებში ხმოვანი ფოსტა ან გადარეკვა. სრული კონტროლი dashboard-დან — SSH-ის გარეშე.",
                },
                {
                    "icon": "circle-dot",
                    "title_en": "Recording + post-call review",
                    "title_ka": "ჩაწერა + ზარის შემდგომ შეფასება",
                    "description_en": "Every call is recorded and stored on your server. Customer ratings via callback IVR or SMS — feeds the same rating-statistics dashboard as your chat reviews.",
                    "description_ka": "ყველა ზარი იწერება და ინახება თქვენს სერვერზე. კლიენტთა შეფასება IVR-ის ან SMS-ის საშუალებით — იგივე rating-statistics dashboard-ს კვებავს, რასაც ჩატის შეფასებები.",
                },
                {
                    "icon": "server-cog",
                    "title_en": "Bring your own Asterisk",
                    "title_ka": "მოიტანე საკუთარი Asterisk",
                    "description_en": "Full BYO Asterisk 18+ support: a one-line install script wires your server into our realtime DB. Trunks, queues, extensions — all driven from the EchoDesk admin panel.",
                    "description_ka": "Asterisk 18+ BYO სრული მხარდაჭერა: ერთი ხაზის ინსტალაციის სკრიპტი თქვენს სერვერს უკავშირებს ჩვენს realtime DB-ს. Trunks, queues, extensions — ყველა მართულია EchoDesk-ის ადმინ პანელიდან.",
                },
            ],
        },
        {
            "type": "checklist",
            "heading_en": "Per-call you get",
            "heading_ka": "ყოველი ზარისთვის",
            "items": [
                {"text_en": "Customer card pop with past tickets, invoices, and chats.", "text_ka": "კლიენტის ბარათი — წარსული ტიკეტები, ინვოისები, საუბრები."},
                {"text_en": "Live transcript option (where the locale is supported).", "text_ka": "ცოცხალი ტრანსკრიპტი (იმ ენებზე, სადაც მხარდაჭერილია)."},
                {"text_en": "Hold, transfer (warm or blind), 3-way conference.", "text_ka": "შეჩერება, გადატანა (warm ან blind), 3-მხრივი კონფერენცია."},
                {"text_en": "Outbound from a Georgian DID with caller-ID control.", "text_ka": "გასული ზარები ქართული DID-დან, caller-ID-ის კონტროლით."},
                {"text_en": "Per-agent + per-queue stats (volume, abandonment, avg talk time).", "text_ka": "ოპერატორისა და რიგის სტატისტიკა (მოცულობა, გაუცემელი ზარები, საშუალო ხანგრძლივობა)."},
            ],
        },
    ],
    "faq_items": [
        {
            "question_en": "Do I need to run my own Asterisk?",
            "question_ka": "საკუთარი Asterisk მჭირდება?",
            "answer_en": "Optional. We host a shared PBX for tenants who don't want infrastructure, or you can run your own Asterisk 18+ server and connect it via our install script. Both setups support the same dashboard features.",
            "answer_ka": "სავალდებულო არ არის. ვფლობთ საერთო PBX-ს, თუ ინფრასტრუქტურის მართვა არ გსურთ, ან შეგიძლიათ დააკავშიროთ საკუთარი Asterisk 18+ ჩვენი ინსტალაციის სკრიპტით. ორივე ვარიანტში dashboard-ის ფუნქციონალი იდენტურია.",
        },
        {
            "question_en": "Can I keep my existing Magti / Silknet number?",
            "question_ka": "ჩემი არსებული Magti-ს / Silknet-ის ნომერი შემიძლია შევინახო?",
            "answer_en": "Yes. We connect to any SIP-capable trunk — Magti, Silknet, Caucasus Online, or international providers. Your DID stays with you.",
            "answer_ka": "კი. ვუერთდებით ნებისმიერ SIP-ტრანკს — Magti, Silknet, Caucasus Online ან საერთაშორისო პროვაიდერები. თქვენი DID თქვენთან რჩება.",
        },
        {
            "question_en": "Where are recordings stored?",
            "question_ka": "სად ინახება ჩანაწერები?",
            "answer_en": "On your Asterisk server (BYO setup) or in DigitalOcean Spaces (Frankfurt EU) for the shared PBX. Retention and access controls are configurable per tenant.",
            "answer_ka": "თქვენი Asterisk სერვერზე (BYO) ან DigitalOcean Spaces-ზე (ფრანკფურტი, EU) — საერთო PBX-ის შემთხვევაში. ხანგრძლივობა და წვდომის კონტროლი კონფიგურირდება ტენანტისთვის ცალკე.",
        },
    ],
}


PAGES = [WHATSAPP_PAGE, INVOICING_PAGE, PBX_PAGE]


def upsert_pages(apps, schema_editor):
    LandingPage = apps.get_model("landing_pages", "LandingPage")
    now = timezone.now()
    for page in PAGES:
        LandingPage.objects.update_or_create(
            slug=page["slug"],
            defaults={
                "page_type": page["page_type"],
                "title": page["title"],
                "hero_subtitle": page["hero_subtitle"],
                "summary": page["summary"],
                "meta_title": page["meta_title"],
                "meta_description": page["meta_description"],
                "keywords": page["keywords"],
                "og_tag": page["og_tag"],
                "highlighted_feature_slugs": page["highlighted_feature_slugs"],
                "content_blocks": page["content_blocks"],
                "faq_items": page["faq_items"],
                "competitor_name": "",
                "comparison_matrix": [],
                "status": "published",
                "published_at": now,
                "generated_by_ai": False,
            },
        )


def noop_reverse(apps, schema_editor):
    # Don't auto-delete on reverse — content has SEO value once published.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("landing_pages", "0002_seed_topics"),
    ]
    operations = [
        migrations.RunPython(upsert_pages, noop_reverse),
    ]
