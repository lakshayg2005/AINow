"""
Check card images before an issue goes out.

A story's og:image is not always a picture of the story: it
can be the author's headshot, a logo or a dead link. Each
card image is downloaded and measured; one that is broken,
tiny or a small portrait is swapped for the story's next
image, or dropped so the card shows its designed placeholder.
"""

from __future__ import annotations

import asyncio
import io

import httpx
from PIL import Image, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RawItem, Story
from app.ingest.http import make_client
from app.schemas.issue import IssueContent
from app.stories.scoring import image_candidates


MAX_IMAGE_BYTES = 8_000_000

# Hero images are wide banners (og:image is usually 1200x630).
MIN_WIDTH = 400
MIN_HEIGHT = 150

# Portrait images narrower than this are almost always
# headshots or avatars rather than article art.
MIN_PORTRAIT_WIDTH = 700


def acceptable_size(
    width: int,
    height: int,
) -> bool:
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return False

    if height > width and width < MIN_PORTRAIT_WIDTH:
        return False

    return True


class Unreachable(Exception):
    """The host timed out or failed; says nothing about the image."""


async def _measure(
    client: httpx.AsyncClient,
    url: str,
) -> tuple[int, int] | None:
    """
    (width, height), or None if the URL is definitely not a
    usable raster image. Raises Unreachable on network errors
    and 5xx/429, which are usually temporary.
    """

    try:
        async with client.stream("GET", url) as response:
            if response.status_code == 429 or response.status_code >= 500:
                raise Unreachable(f"HTTP {response.status_code}")

            if response.status_code != 200:
                return None

            content_type = response.headers.get("content-type", "").lower()

            # SVG does not render in most email clients.
            if not content_type.startswith("image/") or "svg" in content_type:
                return None

            data = bytearray()

            async for chunk in response.aiter_bytes():
                data.extend(chunk)

                if len(data) > MAX_IMAGE_BYTES:
                    return None

    except httpx.HTTPError as error:
        raise Unreachable(type(error).__name__) from error

    try:
        with Image.open(io.BytesIO(bytes(data))) as image:
            return image.size
    except (UnidentifiedImageError, OSError):
        return None


class ImageChecker:
    """Measures each URL once per issue."""

    def __init__(
        self,
        client: httpx.AsyncClient,
    ) -> None:
        self.client = client
        self._results: dict[str, bool] = {}

    async def ok(
        self,
        url: str,
    ) -> bool:
        if url not in self._results:
            self._results[url] = await self._check(url)

        return self._results[url]

    async def _check(
        self,
        url: str,
    ) -> bool:
        for attempt in range(2):
            try:
                size = await _measure(self.client, url)
                break
            except Unreachable as error:
                if attempt == 0:
                    await asyncio.sleep(1)
                    continue

                # Can't tell; keep it; the web page falls back
                # to a placeholder if it really is broken.
                print(f"[Images] Unreachable ({error}), kept: {url}")
                return True

        if size is None:
            print(f"[Images] Unusable: {url}")
            return False

        if not acceptable_size(*size):
            print(f"[Images] Rejected {size[0]}x{size[1]}: {url}")
            return False

        return True


def _story_images(
    db: Session,
    story_id: int,
) -> list[str]:
    story = db.get(Story, story_id)

    if story is None:
        return []

    items = db.scalars(
        select(RawItem).where(RawItem.story_id == story_id)
    ).all()

    return image_candidates(list(items), story.title)


async def vet_images(
    db: Session,
    content: IssueContent,
) -> int:
    """
    Replace or drop bad card images in place. Returns how
    many cards changed. Two cards never share one image.
    """

    cards = (
        ([content.deep_dive] if content.deep_dive else [])
        + list(content.quick_news)
        + ([content.paper_of_week] if content.paper_of_week else [])
        + list(content.research_spotlight)
        + list(content.resources)
    )

    changed = 0
    used: set[str] = set()

    async with make_client() as client:
        checker = ImageChecker(client)

        # Measure every first choice in parallel; fallbacks are rare.
        await asyncio.gather(
            *(checker.ok(card.image_url) for card in cards if card.image_url)
        )

        for card in cards:
            # Cards without an image try their story's images
            # too (a re-check can restore one dropped earlier).
            options = ([card.image_url] if card.image_url else []) + [
                url for url in _story_images(db, card.story_id) if url != card.image_url
            ]

            if not options:
                continue

            chosen = None

            for url in options:
                if url not in used and await checker.ok(url):
                    chosen = url
                    break

            if chosen != card.image_url:
                changed += 1
                card.image_url = chosen

            if chosen:
                used.add(chosen)

    return changed
