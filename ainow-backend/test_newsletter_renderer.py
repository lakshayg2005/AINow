from app.schemas.newsletter import (
    NewsletterContent,
    QuickNewsItem,
)
from app.services.newsletter_renderer import (
    render_newsletter_html,
)


newsletter = NewsletterContent(
    quick_news=[
        QuickNewsItem(
            headline="Example AI development",
            summary="This is a test newsletter item.",
            why_it_matters="It demonstrates the HTML renderer.",
            source_urls=[
                "https://example.com"
            ],
        )
    ],
    our_take="AINow turns complex AI developments into concise insights.",
    source_urls=[
        "https://example.com"
    ],
)

html = render_newsletter_html(
    newsletter,
    title="AINow Test Edition",
)

with open(
    "test_newsletter.html",
    "w",
    encoding="utf-8",
) as file:
    file.write(html)

print(
    "Generated test_newsletter.html"
)