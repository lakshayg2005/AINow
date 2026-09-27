"""
Email rendering for v2 issues.

Email clients ignore <style> blocks and JavaScript to varying
degrees, so this uses table layout and inline styles only.
The interactive version lives on the website; every email
links to it.
"""

from __future__ import annotations

from html import escape

from app.schemas.issue import (
    ConceptCard,
    DeepDiveCard,
    Engagement,
    IssueContent,
    QuickNewsCard,
    ResearchCard,
    ResourceCard,
    SourceRef,
    TrendCard,
)


INK = "#0f172a"
MUTED = "#475569"
FAINT = "#94a3b8"
LINE = "#e2e8f0"
PAPER = "#ffffff"
CANVAS = "#f1f5f9"
ACCENT = "#4f46e5"
ACCENT_SOFT = "#eef2ff"

FONT = "-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"

CATEGORY_STYLES = {
    "model_release": ("Model release", "#4f46e5", "#eef2ff"),
    "product": ("Product", "#0369a1", "#e0f2fe"),
    "research": ("Research", "#047857", "#d1fae5"),
    "policy": ("Policy", "#b45309", "#fef3c7"),
    "safety": ("Safety", "#b91c1c", "#fee2e2"),
    "industry": ("Industry", "#334155", "#f1f5f9"),
    "benchmark": ("Benchmark", "#7c3aed", "#ede9fe"),
    "open_source": ("Open source", "#15803d", "#dcfce7"),
    "tool": ("Tool", "#0f766e", "#ccfbf1"),
}


# ============================================================
# Small pieces
# ============================================================

def _e(value: str | None) -> str:
    return escape(value or "", quote=True)


def _pill(label: str, color: str, background: str) -> str:
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:999px;'
        f"background:{background};color:{color};font-size:11px;font-weight:700;"
        f'letter-spacing:.04em;text-transform:uppercase;">{_e(label)}</span>'
    )


def _category_pill(category: str) -> str:
    label, color, background = CATEGORY_STYLES.get(
        category,
        (category.replace("_", " ").title() or "News", "#334155", "#f1f5f9"),
    )
    return _pill(label, color, background)


def _engagement(engagement: Engagement) -> str:
    parts = []

    if engagement.hn_points:
        parts.append(f"▲ {engagement.hn_points:,} on Hacker News")
    if engagement.hf_upvotes:
        parts.append(f"▲ {engagement.hf_upvotes:,} upvotes on HF Papers")
    if engagement.stars:
        parts.append(f"★ {engagement.stars:,} stars")
    if engagement.likes:
        parts.append(f"♥ {engagement.likes:,} likes")
    if engagement.source_count > 1:
        parts.append(f"{engagement.source_count} sources")

    if not parts:
        return ""

    return (
        f'<div style="margin-top:12px;color:{FAINT};font-size:12px;">'
        + " &nbsp;·&nbsp; ".join(parts)
        + "</div>"
    )


def _refs(refs: list[int], sources: dict[int, SourceRef]) -> str:
    links = [
        f'<a href="{_e(sources[ref].url)}" style="color:{ACCENT};text-decoration:none;'
        f'font-size:12px;font-weight:600;">[{ref}] {_e(sources[ref].source_name)}</a>'
        for ref in refs
        if ref in sources
    ]

    if not links:
        return ""

    return (
        '<div style="margin-top:12px;">'
        + " &nbsp; ".join(links)
        + "</div>"
    )


def _image(url: str | None, alt: str, radius: int = 12) -> str:
    if not url:
        return ""

    return (
        f'<img src="{_e(url)}" alt="{_e(alt)}" width="568" '
        # max-height/object-fit crop tall portraits where supported
        # (Apple Mail, Gmail); other clients show the full image.
        f'style="display:block;width:100%;max-width:568px;height:auto;max-height:300px;'
        f'object-fit:cover;border-radius:{radius}px;margin:0 0 16px;border:1px solid {LINE};">'
    )


def _p(text: str, size: int = 15, color: str = MUTED, margin: str = "8px 0 0") -> str:
    if not text:
        return ""

    return (
        f'<p style="margin:{margin};font-size:{size}px;line-height:1.65;'
        f'color:{color};">{_e(text)}</p>'
    )


def _labelled(label: str, text: str) -> str:
    if not text:
        return ""

    return (
        f'<p style="margin:10px 0 0;font-size:15px;line-height:1.65;color:{MUTED};">'
        f'<strong style="color:{INK};">{_e(label)}</strong> {_e(text)}</p>'
    )


def _why(text: str) -> str:
    if not text:
        return ""

    return (
        f'<div style="margin-top:14px;padding:12px 14px;border-left:3px solid {ACCENT};'
        f'background:{ACCENT_SOFT};border-radius:0 8px 8px 0;font-size:14px;'
        f'line-height:1.6;color:{INK};"><strong>Why it matters:</strong> {_e(text)}</div>'
    )


def _card(inner: str, border: str = LINE, background: str = PAPER) -> str:
    return (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" '
        f'style="margin:0 0 16px;border:1px solid {border};border-radius:14px;'
        f'background:{background};"><tr><td style="padding:20px;">{inner}</td></tr></table>'
    )


def _section(eyebrow: str, title: str, body: str, anchor: str) -> str:
    if not body:
        return ""

    return (
        f'<tr><td id="{anchor}" style="padding:28px 32px 4px;">'
        f'<div style="color:{ACCENT};font-size:12px;font-weight:800;letter-spacing:.14em;'
        f'text-transform:uppercase;">{_e(eyebrow)}</div>'
        f'<h2 style="margin:6px 0 16px;font-size:24px;line-height:1.25;color:{INK};">{_e(title)}</h2>'
        f"{body}</td></tr>"
    )


# ============================================================
# Cards
# ============================================================

def _quick_news(card: QuickNewsCard, sources) -> str:
    pills = _category_pill(card.category)

    if card.is_update:
        pills += " " + _pill("Update", "#9a3412", "#ffedd5")

    return _card(
        _image(card.image_url, card.headline)
        + pills
        + f'<h3 style="margin:10px 0 0;font-size:19px;line-height:1.35;color:{INK};">{_e(card.headline)}</h3>'
        + _p(card.summary)
        + _why(card.why_it_matters)
        + _engagement(card.engagement)
        + _refs(card.refs, sources)
    )


def _research(card: ResearchCard, sources, featured: bool = False) -> str:
    authors = ", ".join(card.authors[:4])

    if len(card.authors) > 4:
        authors += " et al."

    title = card.title

    if card.paper_url:
        title_html = (
            f'<a href="{_e(card.paper_url)}" style="color:{INK};text-decoration:none;">{_e(title)}</a>'
        )
    else:
        title_html = _e(title)

    inner = (
        (_image(card.image_url, title) if featured else "")
        + f'<h3 style="margin:0;font-size:{22 if featured else 18}px;line-height:1.35;color:{INK};">{title_html}</h3>'
        + (f'<div style="margin-top:4px;color:{FAINT};font-size:13px;">{_e(authors)}</div>' if authors else "")
        + _labelled("Problem:", card.problem)
        + _labelled("Idea:", card.core_idea)
        + _labelled("Result:", card.key_result)
        + _why(card.why_it_matters)
        + _engagement(card.engagement)
        + _refs(card.refs, sources)
    )

    if featured:
        return _card(inner, border=ACCENT, background="#fafaff")

    return _card(inner)


def _deep_dive(card: DeepDiveCard, sources) -> str:
    body = (
        _image(card.image_url, card.title)
        + f'<h3 style="margin:0;font-size:22px;line-height:1.3;color:{INK};">{_e(card.title)}</h3>'
        + _p(card.introduction, size=16, color=INK)
    )

    for section in card.sections:
        body += (
            f'<h4 style="margin:18px 0 0;font-size:15px;color:{INK};">{_e(section.heading)}</h4>'
            + _p(section.body)
        )

    return _card(body + _refs(card.refs, sources))


def _trend(index: int, card: TrendCard, sources) -> str:
    return _card(
        f'<div style="color:{ACCENT};font-size:28px;font-weight:800;line-height:1;">0{index}</div>'
        + f'<h3 style="margin:8px 0 0;font-size:18px;color:{INK};">{_e(card.title)}</h3>'
        + _p(card.explanation)
        + _labelled("Evidence:", card.evidence)
        + _refs(card.refs, sources)
    )


def _concept(card: ConceptCard) -> str:
    return _card(
        f'<h3 style="margin:0;font-size:22px;color:{INK};">{_e(card.concept)}</h3>'
        + f'<div style="margin-top:14px;padding:14px;border-radius:10px;background:{CANVAS};">'
        + f'<div style="font-size:12px;font-weight:700;color:{FAINT};text-transform:uppercase;letter-spacing:.08em;">In plain words</div>'
        + _p(card.simple_explanation, color=INK, margin="6px 0 0")
        + "</div>"
        + f'<div style="margin-top:10px;padding:14px;border-radius:10px;background:{CANVAS};">'
        + f'<div style="font-size:12px;font-weight:700;color:{FAINT};text-transform:uppercase;letter-spacing:.08em;">Under the hood</div>'
        + _p(card.technical_explanation, color=INK, margin="6px 0 0")
        + "</div>"
        + _labelled("Example:", card.example)
    )


def _resource(card: ResourceCard, sources) -> str:
    return _card(
        _image(card.image_url, card.name)
        + _pill(card.resource_type, "#0f766e", "#ccfbf1")
        + f'<h3 style="margin:10px 0 0;font-size:18px;color:{INK};">{_e(card.name)}</h3>'
        + _p(card.description)
        + _labelled("Try it if:", card.why_useful)
        + _engagement(card.engagement)
        + f'<a href="{_e(card.url)}" style="display:inline-block;margin-top:14px;padding:10px 16px;'
        f'border-radius:8px;background:{INK};color:#ffffff;font-size:14px;font-weight:600;'
        f'text-decoration:none;">Open {_e(card.resource_type)} →</a>'
    )


# ============================================================
# Issue
# ============================================================

def render_issue_email(
    content: IssueContent,
    web_url: str,
    manage_url: str | None = None,
    unsubscribe_url: str | None = None,
) -> str:
    sources = {ref.id: ref for ref in content.sources}
    date = f"{content.issue_date:%B} {content.issue_date.day}, {content.issue_date.year}"

    toc = [
        label
        for label, present in (
            ("Quick News", content.quick_news),
            ("Research", content.research_spotlight or content.paper_of_week),
            ("Deep Dive", content.deep_dive),
            ("Trends", content.trends),
            ("Learn", content.concept),
            ("Tools", content.resources),
            ("Our Take", content.our_take),
        )
        if present
    ]

    research_body = ""

    if content.paper_of_week:
        research_body += (
            f'<div style="margin:0 0 8px;font-size:13px;font-weight:700;color:{ACCENT};">⭐ Paper of the Week</div>'
            + _research(content.paper_of_week, sources, featured=True)
        )

    research_body += "".join(_research(card, sources) for card in content.research_spotlight)

    sections = "".join(
        [
            _section("Know", "Quick News", "".join(_quick_news(c, sources) for c in content.quick_news), "news"),
            _section("Know", "Research Spotlight", research_body, "research"),
            _section("Deep Dive", "Story of the Week", _deep_dive(content.deep_dive, sources) if content.deep_dive else "", "deep-dive"),
            _section("Know", "AI Trends", "".join(_trend(i, c, sources) for i, c in enumerate(content.trends, 1)), "trends"),
            _section("Learn", "Concept of the Week", _concept(content.concept) if content.concept else "", "learn"),
            _section("Use", "Tools & Resources", "".join(_resource(c, sources) for c in content.resources), "tools"),
            _section(
                "Our Take",
                "What it all means",
                (
                    f'<div style="padding:18px 20px;border-left:4px solid {INK};background:{CANVAS};'
                    f'border-radius:0 12px 12px 0;font-size:16px;line-height:1.7;color:{INK};font-style:italic;">'
                    f"{_e(content.our_take)}</div>"
                )
                if content.our_take
                else "",
                "take",
            ),
        ]
    )

    source_list = "".join(
        f'<li style="margin:0 0 6px;font-size:13px;line-height:1.5;color:{MUTED};">'
        f'<a href="{_e(ref.url)}" style="color:{ACCENT};text-decoration:none;">{_e(ref.title)}</a>'
        f" — {_e(ref.source_name)}</li>"
        for ref in content.sources
    )

    stats = content.stats
    stats_line = (
        f"Curated from {stats.items_scanned:,} items across {stats.stories_considered} stories "
        f"this week · {stats.sources_used} sources cited"
    )

    manage = (
        f' · <a href="{_e(manage_url)}" style="color:{FAINT};">Manage subscription</a>'
        if manage_url
        else ""
    )

    if unsubscribe_url:
        manage += (
            f' · <a href="{_e(unsubscribe_url)}" style="color:{FAINT};">Unsubscribe</a>'
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="color-scheme" content="light">
<title>{_e(content.title)}</title>
</head>
<body style="margin:0;padding:0;background:{CANVAS};font-family:{FONT};">
<div style="display:none;max-height:0;overflow:hidden;opacity:0;">{_e(content.headline)} — {_e(content.intro)}</div>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{CANVAS};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:632px;background:{PAPER};border-radius:18px;overflow:hidden;border:1px solid {LINE};">

<tr><td style="padding:20px 32px;background:{INK};">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
    <td style="color:#ffffff;font-size:20px;font-weight:800;letter-spacing:-.02em;">AI<span style="color:#a5b4fc;">Now</span></td>
    <td align="right" style="font-size:13px;"><a href="{_e(web_url)}" style="color:#c7d2fe;text-decoration:none;">Read on the web →</a></td>
  </tr></table>
</td></tr>

<tr><td style="padding:32px 32px 8px;">
  <div style="color:{FAINT};font-size:13px;font-weight:600;">{_e(date)}</div>
  <h1 style="margin:8px 0 0;font-size:30px;line-height:1.2;letter-spacing:-.02em;color:{INK};">{_e(content.headline or content.title)}</h1>
  {_p(content.intro, size=16, margin="14px 0 0")}
  <div style="margin-top:16px;font-size:13px;color:{FAINT};">In this issue: {_e(" · ".join(toc))}</div>
</td></tr>

{sections}

<tr><td style="padding:24px 32px 8px;">
  <div style="color:{FAINT};font-size:12px;font-weight:800;letter-spacing:.14em;text-transform:uppercase;">Sources</div>
  <ol style="margin:12px 0 0;padding-left:20px;">{source_list}</ol>
</td></tr>

<tr><td style="padding:24px 32px 32px;border-top:1px solid {LINE};">
  <p style="margin:0;font-size:12px;line-height:1.6;color:{FAINT};">{_e(stats_line)}</p>
  <p style="margin:6px 0 0;font-size:12px;line-height:1.6;color:{FAINT};">
    You're receiving this because you subscribed to AINow.
    <a href="{_e(web_url)}" style="color:{FAINT};">View online</a>{manage}
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""



# ============================================================
# Plain-text alternative
# ============================================================

def render_issue_text(
    content: IssueContent,
    web_url: str,
    unsubscribe_url: str | None = None,
) -> str:
    """
    Plain-text version of the issue: shown by text-only
    clients, and HTML-only mail scores worse with spam filters.
    """

    date = f"{content.issue_date:%B} {content.issue_date.day}, {content.issue_date.year}"
    sources = {ref.id: ref for ref in content.sources}

    def refs(ids: list[int]) -> str:
        return " ".join(f"[{ref}]" for ref in ids if ref in sources)

    lines = [
        f"AINow — {date}",
        "",
        content.headline or content.title,
        "",
        content.intro,
        "",
        f"Read on the web: {web_url}",
    ]

    def section(title: str) -> None:
        lines.extend(["", "=" * 60, title.upper(), "=" * 60])

    if content.quick_news:
        section("Quick News")

        for card in content.quick_news:
            prefix = "UPDATE: " if card.is_update else ""
            lines.extend(["", f"* {prefix}{card.headline}", f"  {card.summary}"])

            if card.why_it_matters:
                lines.append(f"  Why it matters: {card.why_it_matters}")

            lines.append(f"  {refs(card.refs)}")

    papers = ([content.paper_of_week] if content.paper_of_week else []) + list(content.research_spotlight)

    if papers:
        section("Research Spotlight")

        for index, card in enumerate(papers):
            star = "PAPER OF THE WEEK: " if content.paper_of_week and index == 0 else ""
            lines.extend(["", f"* {star}{card.title}"])

            for label, value in (
                ("Problem", card.problem),
                ("Idea", card.core_idea),
                ("Result", card.key_result),
            ):
                if value:
                    lines.append(f"  {label}: {value}")

            if card.paper_url:
                lines.append(f"  {card.paper_url}")

    if content.deep_dive:
        dive = content.deep_dive
        section(f"Deep Dive: {dive.title}")
        lines.extend(["", dive.introduction])

        for part in dive.sections:
            lines.extend(["", part.heading, part.body])

        lines.append(refs(dive.refs))

    if content.trends:
        section("AI Trends")

        for index, card in enumerate(content.trends, start=1):
            lines.extend(["", f"{index}. {card.title}", f"   {card.explanation}"])

    if content.concept:
        concept = content.concept
        section(f"Concept of the Week: {concept.concept}")
        lines.extend(["", concept.simple_explanation, "", concept.technical_explanation])

    if content.resources:
        section("Tools & Resources")

        for card in content.resources:
            lines.extend(["", f"* {card.name} ({card.resource_type})", f"  {card.description}", f"  {card.url}"])

    if content.our_take:
        section("Our Take")
        lines.extend(["", content.our_take])

    if content.sources:
        section("Sources")
        lines.append("")
        lines.extend(f"[{ref.id}] {ref.title} — {ref.url}" for ref in content.sources)

    lines.extend(["", "-" * 60, "You're receiving this because you subscribed to AINow."])

    if unsubscribe_url:
        lines.append(f"Unsubscribe: {unsubscribe_url}")

    return "\n".join(lines) + "\n"
