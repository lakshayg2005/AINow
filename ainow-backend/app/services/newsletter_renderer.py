from html import escape

from app.schemas.newsletter import NewsletterContent


def render_newsletter_html(
    newsletter: NewsletterContent,
    title: str = "AINow — AI Weekly",
) -> str:

    quick_news_html = ""

    for item in newsletter.quick_news:
        sources = "".join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            for url in item.source_urls
        )

        quick_news_html += f"""
        <article class="card">
            <div class="eyebrow">QUICK NEWS</div>
            <h3>{escape(item.headline)}</h3>

            <p>{escape(item.summary)}</p>

            <div class="why">
                <strong>Why it matters:</strong>
                {escape(item.why_it_matters)}
            </div>

            <div class="sources">
                {sources}
            </div>
        </article>
        """

    research_html = ""

    for item in newsletter.research_spotlight:
        sources = "".join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            for url in item.source_urls
        )

        research_html += f"""
        <article class="research-card">
            <div class="eyebrow">RESEARCH SPOTLIGHT</div>

            <h3>{escape(item.title)}</h3>

            <p>
                <strong>Problem:</strong>
                {escape(item.problem)}
            </p>

            <p>
                <strong>Core idea:</strong>
                {escape(item.core_idea)}
            </p>

            <p>
                <strong>Key result:</strong>
                {escape(item.key_result)}
            </p>

            <div class="why">
                <strong>Why it matters:</strong>
                {escape(item.why_it_matters)}
            </div>

            <div class="sources">
                {sources}
            </div>
        </article>
        """

    paper_of_week_html = ""

    if newsletter.paper_of_week:
        item = newsletter.paper_of_week

        sources = "".join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            for url in item.source_urls
        )

        paper_of_week_html = f"""
        <section class="featured">
            <div class="eyebrow">⭐ PAPER OF THE WEEK</div>

            <h2>{escape(item.title)}</h2>

            <p>
                <strong>Problem:</strong>
                {escape(item.problem)}
            </p>

            <p>
                <strong>Core idea:</strong>
                {escape(item.core_idea)}
            </p>

            <p>
                <strong>Key result:</strong>
                {escape(item.key_result)}
            </p>

            <p>
                <strong>Why it matters:</strong>
                {escape(item.why_it_matters)}
            </p>

            <div class="sources">
                {sources}
            </div>
        </section>
        """

    deep_dive_html = ""

    if newsletter.deep_dive:
        item = newsletter.deep_dive

        sources = "".join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            for url in item.source_urls
        )

        deep_dive_html = f"""
        <section class="deep-dive">
            <div class="eyebrow">AI DEEP DIVE</div>

            <h2>{escape(item.title)}</h2>

            <p>{escape(item.introduction)}</p>

            <h4>Background</h4>
            <p>{escape(item.background)}</p>

            <h4>Technical Explanation</h4>
            <p>{escape(item.technical_explanation)}</p>

            <h4>Impact</h4>
            <p>{escape(item.impact)}</p>

            <h4>What to Watch</h4>
            <p>{escape(item.what_to_watch)}</p>

            <div class="sources">
                {sources}
            </div>
        </section>
        """

    trends_html = ""

    for item in newsletter.trends:
        sources = "".join(
            f'<a href="{escape(url)}" target="_blank" rel="noopener noreferrer">Source</a>'
            for url in item.source_urls
        )

        trends_html += f"""
        <article class="card">
            <div class="eyebrow">AI TREND</div>

            <h3>{escape(item.title)}</h3>

            <p>{escape(item.explanation)}</p>

            <p>
                <strong>Evidence:</strong>
                {escape(item.evidence)}
            </p>

            <div class="sources">
                {sources}
            </div>
        </article>
        """

    concept_html = ""

    if newsletter.concept:
        concept = newsletter.concept

        concept_html = f"""
        <section class="learn">
            <div class="eyebrow">LEARN</div>

            <h2>{escape(concept.concept)}</h2>

            <p>
                <strong>In simple terms:</strong>
                {escape(concept.simple_explanation)}
            </p>

            <p>
                <strong>Technical view:</strong>
                {escape(concept.technical_explanation)}
            </p>

            <div class="example">
                <strong>Example:</strong>
                {escape(concept.example)}
            </div>
        </section>
        """

    resources_html = ""

    for resource in newsletter.resources:
        resources_html += f"""
        <article class="resource">
            <div class="eyebrow">
                {escape(resource.resource_type)}
            </div>

            <h3>{escape(resource.name)}</h3>

            <p>{escape(resource.description)}</p>

            <p>
                <strong>Why useful:</strong>
                {escape(resource.why_useful)}
            </p>

            <a
                href="{escape(resource.url)}"
                target="_blank"
                rel="noopener noreferrer"
            >
                Visit Resource →
            </a>
        </article>
        """

    source_html = ""

    for url in newsletter.source_urls:
        source_html += f"""
        <li>
            <a
                href="{escape(url)}"
                target="_blank"
                rel="noopener noreferrer"
            >
                {escape(url)}
            </a>
        </li>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>{escape(title)}</title>

    <style>
        * {{
            box-sizing: border-box;
        }}

        body {{
            margin: 0;
            background: #0a0a0a;
            color: #f5f5f5;
            font-family:
                Arial,
                Helvetica,
                sans-serif;
            line-height: 1.7;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
            padding: 60px 24px;
        }}

        .hero {{
            padding: 70px 0;
            border-bottom: 1px solid #292929;
        }}

        .brand {{
            font-size: 15px;
            letter-spacing: 0.2em;
            color: #888;
            text-transform: uppercase;
        }}

        h1 {{
            margin: 18px 0 0;
            font-size: 52px;
            line-height: 1.05;
            letter-spacing: -0.04em;
        }}

        h2 {{
            font-size: 32px;
            line-height: 1.2;
            margin-top: 12px;
        }}

        h3 {{
            font-size: 22px;
            line-height: 1.3;
        }}

        h4 {{
            margin-bottom: 4px;
            font-size: 16px;
        }}

        p {{
            color: #bdbdbd;
        }}

        .section {{
            padding: 55px 0;
        }}

        .section-title {{
            margin-bottom: 25px;
            font-size: 13px;
            color: #777;
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }}

        .card,
        .research-card,
        .resource {{
            padding: 28px;
            margin-bottom: 18px;
            border: 1px solid #292929;
            border-radius: 18px;
            background: #101010;
        }}

        .featured {{
            margin: 25px 0;
            padding: 36px;
            border: 1px solid #444;
            border-radius: 22px;
            background: #151515;
        }}

        .deep-dive {{
            margin: 25px 0;
            padding: 36px;
            border-left: 3px solid #777;
            background: #111;
        }}

        .learn {{
            padding: 36px;
            border-radius: 22px;
            background: #151515;
        }}

        .example {{
            margin-top: 20px;
            padding: 18px;
            border-radius: 12px;
            background: #0d0d0d;
        }}

        .why {{
            margin-top: 18px;
            padding: 16px 18px;
            border-left: 2px solid #555;
            background: #0c0c0c;
            color: #cfcfcf;
        }}

        .eyebrow {{
            color: #777;
            font-size: 12px;
            font-weight: 700;
            letter-spacing: 0.16em;
            text-transform: uppercase;
        }}

        .sources {{
            display: flex;
            flex-wrap: wrap;
            gap: 12px;
            margin-top: 18px;
        }}

        a {{
            color: #f5f5f5;
        }}

        .sources a {{
            font-size: 13px;
            color: #999;
        }}

        .sources a:hover {{
            color: white;
        }}

        .footer {{
            padding-top: 50px;
            margin-top: 50px;
            border-top: 1px solid #292929;
            color: #666;
            font-size: 13px;
        }}

        @media (max-width: 700px) {{
            .container {{
                padding: 35px 18px;
            }}

            h1 {{
                font-size: 38px;
            }}

            h2 {{
                font-size: 27px;
            }}
        }}
    </style>
</head>

<body>

<main class="container">

    <header class="hero">
        <div class="brand">AINow</div>

        <h1>
            The AI newsletter
            without the noise.
        </h1>

        <p>
            Curated AI news, research,
            concepts and tools — explained clearly.
        </p>
    </header>

    <section class="section">
        <div class="section-title">
            Know
        </div>

        {quick_news_html}
    </section>

    <section class="section">
        <div class="section-title">
            Research Spotlight
        </div>

        {research_html}
    </section>

    {paper_of_week_html}

    {deep_dive_html}

    <section class="section">
        <div class="section-title">
            AI Trends
        </div>

        {trends_html}
    </section>

    {concept_html}

    <section class="section">
        <div class="section-title">
            Use
        </div>

        {resources_html}
    </section>

    <section class="section">
        <div class="section-title">
            Our Take
        </div>

        <div class="featured">
            <p>
                {escape(newsletter.our_take)}
            </p>
        </div>
    </section>

    <section class="section">
        <div class="section-title">
            Sources
        </div>

        <ol>
            {source_html}
        </ol>
    </section>

    <footer class="footer">
        <div>
            © 2026 AINow
        </div>

        <div>
            AI information without the noise.
        </div>
    </footer>

</main>

</body>
</html>
"""