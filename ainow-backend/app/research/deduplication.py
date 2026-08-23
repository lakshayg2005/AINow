import re

import numpy as np

from app.core.embeddings import generate_embeddings
from app.schemas.research import ResearchCandidate


SEMANTIC_MERGE_DISTANCE = 0.10


def normalize_title(
    title: str,
) -> str:

    title = title.lower()

    title = re.sub(
        r"[^a-z0-9\s]",
        " ",
        title,
    )

    return " ".join(
        title.split()
    )


def add_supporting_source(
    candidate: ResearchCandidate,
    source_name: str,
) -> None:

    sources = set(
        candidate.supporting_sources
    )

    if source_name:
        sources.add(
            source_name
        )

    candidate.supporting_sources = sorted(
        sources
    )

    candidate.cross_source_count = len(
        sources
    )


def merge_candidate_metadata(
    existing: ResearchCandidate,
    incoming: ResearchCandidate,
) -> None:

    add_supporting_source(
        existing,
        incoming.source_name,
    )

    # Keep the richer text.
    if len(incoming.raw_content) > len(
        existing.raw_content
    ):
        existing.raw_content = (
            incoming.raw_content
        )

    # Keep higher citation count.
    existing.citation_count = max(
        existing.citation_count,
        incoming.citation_count,
    )

    # Merge authors.
    existing.authors = sorted(
        set(
            existing.authors
            + incoming.authors
        )
    )


def merge_candidates(
    candidates: list[ResearchCandidate],
) -> list[ResearchCandidate]:

    if not candidates:
        return []

    # ==================================================
    # 1. Exact URL deduplication
    # ==================================================

    url_map: dict[
        str,
        ResearchCandidate,
    ] = {}

    for candidate in candidates:

        key = (
            candidate.url
            .strip()
            .lower()
            .rstrip("/")
        )

        if key not in url_map:

            add_supporting_source(
                candidate,
                candidate.source_name,
            )

            url_map[key] = candidate

        else:

            merge_candidate_metadata(
                url_map[key],
                candidate,
            )

    candidates = list(
        url_map.values()
    )

    # ==================================================
    # 2. Exact title deduplication
    # ==================================================

    title_map: dict[
        str,
        ResearchCandidate,
    ] = {}

    title_unique = []

    for candidate in candidates:

        key = normalize_title(
            candidate.title
        )

        if key not in title_map:

            title_map[key] = candidate
            title_unique.append(
                candidate
            )

        else:

            merge_candidate_metadata(
                title_map[key],
                candidate,
            )

    candidates = title_unique

    # ==================================================
    # 3. Semantic merging
    # ==================================================

    if len(candidates) <= 1:
        return candidates

    texts = [
        (
            f"{candidate.title}\n"
            f"{candidate.raw_content}"
        )
        for candidate in candidates
    ]

    embeddings = np.asarray(
        generate_embeddings(texts)
    )

    merged: list[ResearchCandidate] = []
    merged_embeddings: list[np.ndarray] = []

    for index, candidate in enumerate(
        candidates
    ):

        current_embedding = embeddings[index]

        best_index = None
        best_distance = float("inf")

        for merged_index, existing_embedding in enumerate(
            merged_embeddings
        ):

            similarity = float(
                np.dot(
                    current_embedding,
                    existing_embedding,
                )
            )

            distance = 1.0 - similarity

            if distance < best_distance:

                best_distance = distance
                best_index = merged_index

        if (
            best_index is not None
            and best_distance
            <= SEMANTIC_MERGE_DISTANCE
        ):

            merge_candidate_metadata(
                merged[best_index],
                candidate,
            )

        else:

            add_supporting_source(
                candidate,
                candidate.source_name,
            )

            merged.append(
                candidate
            )

            merged_embeddings.append(
                current_embedding
            )

    return merged