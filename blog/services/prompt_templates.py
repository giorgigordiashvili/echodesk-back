"""Prompt construction for the blog-post AI generator.

One `system` prompt (constant) plus a per-post-type `user` prompt
builder. The system prompt pins Claude to a strict JSON schema so
parsing the response is deterministic. User prompts vary the content
structure (sections, depth) by post type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from blog.models import BlogTopic


SYSTEM_PROMPT = """You write long-form SEO-optimized blog posts for EchoDesk — an \
all-in-one business platform for Georgian small- and mid-size businesses. \
EchoDesk bundles: WhatsApp, Messenger, Instagram, email, and SIP phone calls into \
one shared inbox; plus ticketing, invoicing (in GEL), booking management, and \
leave/HR tracking. It is hosted in Georgia, billed in Georgian Lari, and fully \
localized in Georgian and English.

Output JSON and ONLY JSON matching this exact schema:

{
  "title_ka": "<string, <= 60 chars>",
  "title_en": "<string, <= 60 chars>",
  "summary_ka": "<string, <= 180 chars>",
  "summary_en": "<string, <= 180 chars>",
  "content_ka_html": "<HTML string, 900-1500 words>",
  "content_en_html": "<HTML string, 900-1500 words>",
  "meta_title_ka": "<string, <= 60 chars>",
  "meta_title_en": "<string, <= 60 chars>",
  "meta_description_ka": "<string, <= 160 chars>",
  "meta_description_en": "<string, <= 160 chars>",
  "faq_items": [
    {
      "question_ka": "<string>",
      "question_en": "<string>",
      "answer_ka": "<string>",
      "answer_en": "<string>"
    }
  ],
  "keywords": ["<string>", "<string>", ...]
}

Hard rules:

1. Return valid JSON. No markdown fences, no commentary, no text outside the \
   JSON object.
2. Both locales must be present. No empty strings.
3. For comparisons: acknowledge competitor strengths honestly. Do NOT invent \
   specific prices, feature names, or bugs for competitors. When uncertain \
   about a specific competitor capability, use hedged phrasing \
   ("typically", "in most plans") rather than concrete claims.
4. Lead with reader pain or a concrete scenario, not product features. \
   Product is the solution revealed in the body, not the opening line.
5. Natural keyword usage only — never keyword-stuff.
6. HTML tags allowed in content_*_html: h2, h3, p, ul, ol, li, strong, em, a, \
   blockquote, code, table, thead, tbody, tr, th, td. No h1 (page renders \
   one h1 outside the content). No script, style, iframe, img.
7. Use <a href="/registration">Start free trial</a> for the primary CTA near \
   the end. Internal links to /pricing, /docs, and /blog are allowed.
8. 4-8 FAQ items. Each answer 40-120 words. Questions phrased as a user \
   would search them.
9. Georgian content must read as native Georgian — do not translate \
   word-for-word from the English version.
"""


def build_user_prompt(topic: "BlogTopic") -> str:
    keywords = ", ".join(topic.target_keywords or []) or "(pick 3-5 naturally from the topic)"
    base = f"""Write a blog post with the following brief.

- Post type: {topic.post_type}
- Primary language target: {topic.primary_language} (Georgian or English — both are generated regardless, but lean the angle toward this audience)
- Slug: {topic.slug}
- Title hints (use as starting point, refine as needed):
  - Georgian: {topic.get_title_hint("ka") or "(propose)"}
  - English: {topic.get_title_hint("en") or "(propose)"}
- Angle: {topic.angle_hint or "(infer from the post type and slug)"}
- Target keywords to weave in naturally: {keywords}
"""

    if topic.post_type == "comparison":
        competitor = topic.competitor_name or "the competitor"
        base += f"""
Competitor: {competitor}

Required H2 sections (in this order):

1. "Who this comparison is for" (2-3 sentences framing the reader — e.g. a Georgian small business weighing EchoDesk vs {competitor}).
2. "Where {competitor} wins" (3-5 bullet list of honest strengths — e.g. bigger global community, more mature WhatsApp template editor, etc. Do not invent specific features).
3. "Where EchoDesk fits better" (5-7 bullets highlighting unique EchoDesk wedges: GEL billing, Georgian-hosted, SIP calling + invoicing + bookings bundled, pay-per-feature pricing, Georgian-language UI).
4. "Feature-by-feature" (HTML <table> with 8-12 rows — comparing modules like Channels, Pricing model, Phone system, Invoicing, Booking, HR, Hosting, Language support. Mark each row "EchoDesk" / "{competitor}" / "Both" in the winner cell).
5. "Which to pick" (scenario-based decision guide with 3-4 typical scenarios).
6. Final CTA paragraph with <a href="/registration">Start free trial</a>.

FAQ items (4-8) should cover questions like:
- Is EchoDesk cheaper than {competitor} in Georgia?
- Can I migrate my data from {competitor} to EchoDesk?
- Does EchoDesk support [specific competitor feature]?
- Can I use EchoDesk in Georgian?
"""
    elif topic.post_type == "how_to":
        base += """
Structure as a practical how-to guide:

1. "What you'll need" (1 paragraph + short bullet list of prerequisites).
2. Numbered H2 sections for each major step (4-8 steps). Each step starts with a clear verb ("Connect your WhatsApp Business account…"). Include concrete tips or common pitfalls as brief callouts.
3. "Troubleshooting" section covering 2-3 typical issues.
4. Final CTA paragraph with <a href="/registration">Start free trial</a> to try it yourself.

FAQ items (4-8) should cover common questions a user would type into Google while performing this task.
"""
    elif topic.post_type == "use_case":
        base += """
Structure as a scenario-based narrative:

1. Open with a specific scenario (e.g. "Ana runs a boutique in Tbilisi with 3 staff and handles orders across Instagram DM, WhatsApp, and phone calls."). Make it concrete.
2. H2 "The problem" — 2-3 specific friction points.
3. H2 "How EchoDesk handles it" — 4-6 numbered points walking through the workflow inside the tool.
4. H2 "The payoff" — 2-3 measurable outcomes (e.g. fewer missed messages, faster response, one tool instead of five).
5. Final CTA paragraph with <a href="/registration">Start free trial</a>.

FAQ items (4-8) should answer questions someone researching this exact use case would ask.
"""
    elif topic.post_type == "announcement":
        base += """
Structure as a product announcement:

1. Lead paragraph — what's new in one sentence, why it matters in the next.
2. H2 "What it does" — the feature walked through concretely (screenshot-ready descriptions).
3. H2 "Who it's for" — ideal customer shape.
4. H2 "How to try it" — 2-3 setup steps.
5. CTA paragraph linking to /registration or /docs.

FAQ items (4-6) covering "Is this extra cost?", "Do I need to do anything to enable it?", etc.
"""
    else:  # thought_leadership
        base += """
Structure as an editorial / thought-leadership piece:

1. A sharp opinion or observation in the opening paragraph.
2. 3-5 H2 sections developing the argument. Can cite Georgian SMB patterns you've observed (hedged — "many Georgian businesses we work with").
3. A counterpoint H2 where you acknowledge the other side honestly.
4. Closing paragraph tying it back to EchoDesk's approach. Include <a href="/registration">Start free trial</a> if natural, skip if forced.

FAQ items (4-6) covering the typical counter-questions this opinion would provoke.
"""

    base += "\nReturn JSON only. Begin your response with `{` and end with `}`."
    return base
