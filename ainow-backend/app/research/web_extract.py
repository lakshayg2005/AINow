from datetime import datetime

import httpx


async def fetch_web_page(
    url: str,
) -> str:

    headers = {
        "User-Agent": (
            "AINow/1.0 "
            "(AI Newsletter Research)"
        )
    }

    async with httpx.AsyncClient(
        timeout=30,
        follow_redirects=True,
        headers=headers,
    ) as client:

        response = await client.get(url)
        response.raise_for_status()

        return response.text


def extract_article_text(
    html: str,
) -> str:
    """
    HTML → clean main article text.

    We will implement the extraction logic
    in the next step.
    """

    raise NotImplementedError