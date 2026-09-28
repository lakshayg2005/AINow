from __future__ import annotations

import asyncio

import httpx


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/139.0 Safari/537.36 "
        "AINowResearch/1.0"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml,application/json;q=0.9,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


def make_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        headers=DEFAULT_HEADERS,
        timeout=httpx.Timeout(
            connect=10.0,
            read=30.0,
            write=10.0,
            pool=30.0,
        ),
        follow_redirects=True,
        limits=httpx.Limits(
            max_connections=20,
        ),
    )


async def get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    attempts: int = 3,
    **kwargs,
) -> httpx.Response:
    """
    GET with exponential backoff on connection errors,
    429 and 5xx. Other 4xx responses raise immediately.
    """

    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            response = await client.get(
                url,
                **kwargs,
            )

            response.raise_for_status()
            return response

        except httpx.HTTPStatusError as error:
            last_error = error
            status = error.response.status_code

            if status != 429 and status < 500:
                raise

        except httpx.TransportError as error:
            last_error = error

        if attempt < attempts:
            await asyncio.sleep(
                2 ** (attempt - 1)
            )

    assert last_error is not None
    raise last_error
