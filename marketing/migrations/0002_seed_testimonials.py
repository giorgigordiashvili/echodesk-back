"""Seed six plausible Georgian SMB testimonials for social proof on /.

User explicitly approved placeholder/fake testimonials for launch — the
strings reference specific shipped functionality (WhatsApp inbox, GEL
billing, call recording, invoicing, bookings) and make no aspirational
claims (no SLAs, no AI routing, no macros). Authors + companies are
fictional; swap for real ones via Django admin once available.
"""

from django.db import migrations


SEEDS = [
    {
        "slug": "salon-elite",
        "position": 10,
        "author_name": "ნინო ქავთარაძე",
        "author_role_ka": "მფლობელი",
        "author_role_en": "Owner",
        "company_name": "Salon Elite",
        "quote_ka": (
            "ყველა მიწერა WhatsApp-იდან, Instagram-იდან და ზარები — ერთ Inbox-ში. "
            "ადრე 3 თანამშრომელი უკვე დაკარგავდა კლიენტებს შუადღისას."
        ),
        "quote_en": (
            "Every WhatsApp, Instagram and phone message — in one inbox. "
            "Before EchoDesk, three staff members would already be losing clients by lunch."
        ),
        "rating": 5,
    },
    {
        "slug": "clinic-nova",
        "position": 20,
        "author_name": "გიორგი ბერიძე",
        "author_role_ka": "კლინიკის დირექტორი",
        "author_role_en": "Clinic Director",
        "company_name": "Nova Clinic",
        "quote_ka": (
            "ჯავშნები და ზარების ჩანაწერები ერთ ადგილზე — რეგისტრატურამ "
            "20%-ით ნაკლებ შეცდომას უშვებს და პაციენტი ზუსტად ხვდება დროულად."
        ),
        "quote_en": (
            "Bookings and call recordings in one place — reception makes 20% fewer "
            "mistakes and patients show up at the right time."
        ),
        "rating": 5,
    },
    {
        "slug": "law-firm-axiom",
        "position": 30,
        "author_name": "თამარ ლომიძე",
        "author_role_ka": "პარტნიორი",
        "author_role_en": "Partner",
        "company_name": "Axiom Legal",
        "quote_ka": (
            "ლარში ინვოისები, Bank of Georgia-ის გადახდები და ზარების ჩანაწერები — "
            "ორი ცალკე სერვისის ნაცვლად ერთი სისტემა. ბუღალტერიამ მადლობა გადაგვიხადა."
        ),
        "quote_en": (
            "GEL invoices, Bank of Georgia checkout and call recordings — one system "
            "instead of two separate services. Our accountant thanked us."
        ),
        "rating": 5,
    },
    {
        "slug": "logistics-karavani",
        "position": 40,
        "author_name": "დავით ჩიკვინიძე",
        "author_role_ka": "ოპერაციული მენეჯერი",
        "author_role_en": "Operations Manager",
        "company_name": "ქარავანი Logistics",
        "quote_ka": (
            "Georgian SIP trunk წინასწარ კონფიგურირებული იყო — გაშვება ერთ დღეში მოვახერხეთ. "
            "დისპეტჩერს ახლა ყველა ზარის ჩანაწერი ტიკეტზე აქვს მიმაგრებული."
        ),
        "quote_en": (
            "The Georgian SIP trunk was preconfigured — we went live in one day. "
            "Dispatch now has every call recording attached to the relevant ticket."
        ),
        "rating": 5,
    },
    {
        "slug": "ecommerce-blackhat",
        "position": 50,
        "author_name": "ანა წიკლაური",
        "author_role_ka": "დამფუძნებელი",
        "author_role_en": "Founder",
        "company_name": "BlackHat Apparel",
        "quote_ka": (
            "Instagram DM, WhatsApp და TikTok Shop ერთ ადგილას. ფასი ლარში — "
            "თვის ბოლოს აღარ ვფიქრობთ, რამდენი უნდა ვიცრიათ კურსიდან."
        ),
        "quote_en": (
            "Instagram DM, WhatsApp and TikTok Shop in one place. Billed in GEL — "
            "we stopped worrying about end-of-month FX hits."
        ),
        "rating": 5,
    },
    {
        "slug": "agency-northpoint",
        "position": 60,
        "author_name": "ლევან ნოდია",
        "author_role_ka": "გამგებელი",
        "author_role_en": "Managing Director",
        "company_name": "NorthPoint Digital",
        "quote_ka": (
            "აგენტობის გუნდი 8 ადამიანიდან გაიზარდა — EchoDesk-მა ტიკეტი+email+ზარი "
            "ერთ სისტემაში შეაერთა. ფუნქციებზე დაფუძნებული ფასი შეგვიძლია ვაკონტროლოთ."
        ),
        "quote_en": (
            "Our agency grew from 8 people — EchoDesk merged tickets + email + calls "
            "into one system. Feature-based pricing is something we can actually control."
        ),
        "rating": 5,
    },
]


def seed(apps, schema_editor):
    Testimonial = apps.get_model("marketing", "Testimonial")
    for row in SEEDS:
        Testimonial.objects.update_or_create(slug=row["slug"], defaults=row)


def unseed(apps, schema_editor):
    Testimonial = apps.get_model("marketing", "Testimonial")
    Testimonial.objects.filter(slug__in=[r["slug"] for r in SEEDS]).delete()


class Migration(migrations.Migration):
    dependencies = [("marketing", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
