from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import httpx

from app.schemas.research import ResearchCandidate


USER_AGENT = "AINow/1.0 (AI Newsletter Research)"

# Put your email here or move it to .env later.
CROSSREF_MAILTO = "lakshay221b@gmail.com"


# =========================================================
# OPENALEX
# =========================================================

async def search_openalex(
    query: str,
    lookback_days: int = 14,
    max_results: int = 20,
) -> list[ResearchCandidate]:

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=lookback_days)
    ).date()

    url = "https://api.openalex.org/works"

    params = {
        "search": query,
        "filter": (
            f"from_publication_date:{cutoff},"
            "has_abstract:true"
        ),
        "sort": "-publication_date",
        "per_page": max_results,
    }

    headers = {
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=headers,
        ) as client:

            response = await client.get(
                url,
                params=params,
            )

            response.raise_for_status()

    except httpx.ConnectError as error:
        raise RuntimeError(
            f"Could not connect to OpenAlex: {error}"
        ) from error

    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"OpenAlex returned HTTP "
            f"{error.response.status_code}"
        ) from error

    except httpx.RequestError as error:
        raise RuntimeError(
            f"OpenAlex request failed: {error}"
        ) from error

    data = response.json()

    candidates = []

    for work in data.get(
        "results",
        [],
    ):

        title = work.get("title")
        work_id = work.get("id")
        publication_date = work.get(
            "publication_date"
        )

        if not title or not work_id:
            continue

        published_at = None

        if publication_date:
            published_at = datetime.fromisoformat(
                publication_date
            ).replace(
                tzinfo=timezone.utc
            )

        # -----------------------------------------
        # Reconstruct abstract
        # -----------------------------------------

        abstract = ""

        abstract_data = work.get(
            "abstract_inverted_index"
        )

        if abstract_data:

            words = []

            for word, positions in abstract_data.items():
                for position in positions:
                    words.append(
                        (position, word)
                    )

            words.sort()

            abstract = " ".join(
                word
                for _, word in words
            )

        # -----------------------------------------
        # Authors
        # -----------------------------------------

        authors = []

        for authorship in work.get(
            "authorships",
            [],
        ):

            author = authorship.get(
                "author",
                {},
            )

            name = author.get("display_name")

            if name:
                authors.append(name)

        # -----------------------------------------
        # OpenAlex citation count
        # -----------------------------------------

        citation_count = work.get(
            "cited_by_count",
            0,
        )

        candidates.append(
            ResearchCandidate(
                title=title,
                url=work_id,
                source_name="OpenAlex",
                category="research",
                raw_content=abstract or title,
                published_at=published_at,
                trust_tier=1,
                topics=[
                    "research",
                    "artificial-intelligence",
                ],
                citation_count=citation_count,
                authors=authors,
            )
        )

    return candidates


# =========================================================
# CROSSREF
# =========================================================

async def search_crossref(
    query: str,
    lookback_days: int = 30,
    max_results: int = 20,
) -> list[ResearchCandidate]:

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=lookback_days)
    ).date()

    url = "https://api.crossref.org/works"

    params = {
        "query.bibliographic": query,
        "filter": (
            f"from-pub-date:{cutoff},"
            "has-abstract:1,"
            "type:journal-article"
        ),
        "sort": "published",
        "order": "desc",
        "rows": max_results,
        "mailto": CROSSREF_MAILTO,
    }

    headers = {
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=headers,
        ) as client:

            response = await client.get(
                url,
                params=params,
            )

            response.raise_for_status()

    except httpx.ConnectError as error:
        raise RuntimeError(
            f"Could not connect to Crossref: {error}"
        ) from error

    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"Crossref returned HTTP "
            f"{error.response.status_code}"
        ) from error

    except httpx.RequestError as error:
        raise RuntimeError(
            f"Crossref request failed: {error}"
        ) from error

    data = response.json()

    candidates = []

    items = (
        data
        .get("message", {})
        .get("items", [])
    )

    for item in items:

        # -----------------------------------------
        # Title
        # -----------------------------------------

        title_list = item.get(
            "title",
            [],
        )

        if not title_list:
            continue

        title = title_list[0].strip()

        # -----------------------------------------
        # Abstract
        # -----------------------------------------

        abstract = item.get(
            "abstract",
            "",
        )

        if abstract:

            import re

            abstract = re.sub(
                r"<[^>]+>",
                " ",
                abstract,
            )

            abstract = " ".join(
                abstract.split()
            )

        # -----------------------------------------
        # URL
        # -----------------------------------------

        doi = item.get("DOI")
        item_url = item.get("URL")

        paper_url = (
            f"https://doi.org/{doi}"
            if doi
            else item_url
        )

        if not paper_url:
            continue

        # -----------------------------------------
        # Publication date
        # -----------------------------------------

        published_at = None

        date_parts = (
            item
            .get("published", {})
            .get("date-parts", [])
        )

        if date_parts and date_parts[0]:

            parts = date_parts[0]

            year = parts[0]
            month = (
                parts[1]
                if len(parts) > 1
                else 1
            )
            day = (
                parts[2]
                if len(parts) > 2
                else 1
            )

            published_at = datetime(
                year,
                month,
                day,
                tzinfo=timezone.utc,
            )

        # -----------------------------------------
        # Authors
        # -----------------------------------------

        authors = []

        for author in item.get(
            "author",
            [],
        ):

            given = author.get(
                "given",
                "",
            )

            family = author.get(
                "family",
                "",
            )

            full_name = (
                f"{given} {family}"
            ).strip()

            if full_name:
                authors.append(full_name)

        # -----------------------------------------
        # Citation count
        # -----------------------------------------

        citation_count = item.get(
            "is-referenced-by-count",
            0,
        )

        candidates.append(
            ResearchCandidate(
                title=title,
                url=paper_url,
                source_name="Crossref",
                category="research",
                raw_content=abstract or title,
                published_at=published_at,
                trust_tier=2,
                topics=["research"],
                citation_count=citation_count,
                authors=authors,
            )
        )

    return candidates


# =========================================================
# arXiv
# =========================================================

async def search_arxiv(
    query: str,
    lookback_days: int = 14,
    max_results: int = 20,
) -> list[ResearchCandidate]:

    # arXiv's API provides Atom/XML search results.
    # We retrieve recent records and perform our
    # stricter AINow relevance filtering afterward.

    params = {
        "search_query": f'all:"{query}"',
        "start": 0,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }

    url = (
        "https://export.arxiv.org/api/query?"
        + urlencode(params)
    )

    headers = {
        "User-Agent": USER_AGENT,
    }

    try:
        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers=headers,
        ) as client:

            response = await client.get(url)

            response.raise_for_status()

    except httpx.ConnectError as error:
        raise RuntimeError(
            f"Could not connect to arXiv: {error}"
        ) from error

    except httpx.HTTPStatusError as error:
        raise RuntimeError(
            f"arXiv returned HTTP "
            f"{error.response.status_code}"
        ) from error

    except httpx.RequestError as error:
        raise RuntimeError(
            f"arXiv request failed: {error}"
        ) from error

    try:
        root = ET.fromstring(
            response.text
        )
    except ET.ParseError as error:
        raise RuntimeError(
            f"Could not parse arXiv response: {error}"
        ) from error

    namespace = {
        "atom": "http://www.w3.org/2005/Atom"
    }

    candidates = []

    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(days=lookback_days)
    )

    for entry in root.findall(
        "atom:entry",
        namespace,
    ):

        title_element = entry.find(
            "atom:title",
            namespace,
        )

        summary_element = entry.find(
            "atom:summary",
            namespace,
        )

        id_element = entry.find(
            "atom:id",
            namespace,
        )

        published_element = entry.find(
            "atom:published",
            namespace,
        )

        if (
            title_element is None
            or summary_element is None
            or id_element is None
        ):
            continue

        title = " ".join(
            title_element.text.strip().split()
        )

        abstract = " ".join(
            summary_element.text.strip().split()
        )

        paper_url = (
            id_element.text.strip()
        )

        published_at = None

        if (
            published_element is not None
            and published_element.text
        ):

            published_at = (
                datetime.fromisoformat(
                    published_element.text
                    .replace(
                        "Z",
                        "+00:00",
                    )
                )
            )

            if published_at < cutoff:
                continue

        # -----------------------------------------
        # Authors
        # -----------------------------------------

        authors = []

        for author in entry.findall(
            "atom:author",
            namespace,
        ):

            name_element = author.find(
                "atom:name",
                namespace,
            )

            if (
                name_element is not None
                and name_element.text
            ):
                authors.append(
                    name_element.text.strip()
                )

        candidates.append(
            ResearchCandidate(
                title=title,
                url=paper_url,
                source_name="arXiv",
                category="research",
                raw_content=abstract,
                published_at=published_at,
                trust_tier=1,
                topics=[
                    "research",
                    "artificial-intelligence",
                ],
                citation_count=0,
                authors=authors,
            )
        )

    return candidates