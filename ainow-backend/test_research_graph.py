import asyncio

from app.graph.research_graph import research_graph


async def main():

    result = await research_graph.ainvoke(
        {
            "topic": "llm",
        }
    )

    # ==================================================
    # RESEARCH RESULTS
    # ==================================================

    ranked = result.get(
        "ranked_candidates",
        []
    )

    print(
        "\nCandidates:",
        len(
            result.get(
                "candidates",
                []
            )
        )
    )

    print(
        "Fresh:",
        len(
            result.get(
                "fresh_candidates",
                []
            )
        )
    )

    print("\nTop candidates:")

    for item in ranked[:10]:

        candidate = item.candidate

        print(
            f"{item.score} | "
            f"{candidate.title} | "
            f"{candidate.source_name} | "
            f"support={candidate.cross_source_count}"
        )

    # ==================================================
    # EDITORIAL SELECTION
    # ==================================================

    selection = result.get(
        "editorial_selection"
    )

    print(
        "\nEDITORIAL SELECTION"
    )

    if selection:

        print(
            "Selected:",
            selection.selected_candidate_indices,
        )

        print(
            "Research Spotlight:",
            selection.research_spotlight_indices,
        )

        print(
            "Paper of Week:",
            selection.paper_of_week_index,
        )

        print(
            "Deep Dive:",
            selection.deep_dive_index,
        )

        print(
            "Trends:",
            selection.trend_indices,
        )

        print(
            "Reasoning:",
            selection.reasoning,
        )

    else:

        print(
            "No editorial selection was produced."
        )

    # ==================================================
    # GENERATED NEWSLETTER
    # ==================================================

    content = result.get(
        "newsletter_content"
    )

    print(
        "\n===== NEWSLETTER ====="
    )

    if not content:

        print(
            "No newsletter content was generated."
        )

        return

    # --------------------------------------------------
    # QUICK NEWS
    # --------------------------------------------------

    print(
        "\nQUICK NEWS:"
    )

    for item in content.quick_news:

        print(
            f"\n{item.headline}"
        )

        print(
            item.summary
        )

        print(
            "Why it matters:",
            item.why_it_matters
        )

    # --------------------------------------------------
    # RESEARCH SPOTLIGHT
    # --------------------------------------------------

    print(
        "\n\nRESEARCH SPOTLIGHT:"
    )

    for item in content.research_spotlight:

        print(
            f"\n{item.title}"
        )

        print(
            "Why it matters:",
            item.why_it_matters
        )

    # --------------------------------------------------
    # PAPER OF THE WEEK
    # --------------------------------------------------

    print(
        "\n\nPAPER OF THE WEEK:"
    )

    if content.paper_of_week:

        print(
            content.paper_of_week.title
        )

        print(
            "Why it matters:",
            content.paper_of_week.why_it_matters
        )

    else:

        print(
            "No Paper of the Week selected."
        )

    # --------------------------------------------------
    # DEEP DIVE
    # --------------------------------------------------

    print(
        "\n\nDEEP DIVE:"
    )

    if content.deep_dive:

        print(
            content.deep_dive.title
        )

        print(
            content.deep_dive.introduction
        )

    else:

        print(
            "No Deep Dive generated."
        )

    # --------------------------------------------------
    # TRENDS
    # --------------------------------------------------

    print(
        "\n\nAI TRENDS:"
    )

    for item in content.trends:

        print(
            f"\n{item.title}"
        )

        print(
            item.explanation
        )

    # --------------------------------------------------
    # AI CONCEPT
    # --------------------------------------------------

    print(
        "\n\nAI CONCEPT:"
    )

    if content.concept:

        print(
            content.concept.concept
        )

        print(
            content.concept.simple_explanation
        )

    else:

        print(
            "No AI concept generated."
        )

    # --------------------------------------------------
    # RESOURCES
    # --------------------------------------------------

    print(
        "\n\nAI RESOURCES:"
    )

    for resource in content.resources:

        print(
            f"\n{resource.name}"
        )

        print(
            resource.description
        )

        print(
            resource.url
        )

    # --------------------------------------------------
    # OUR TAKE
    # --------------------------------------------------

    print(
        "\n\nOUR TAKE:"
    )

    print(
        content.our_take
    )

    # --------------------------------------------------
    # SOURCES
    # --------------------------------------------------

    print(
        "\n\nSOURCES:"
    )

    for url in content.source_urls:

        print(
            url
        )
    print(
    "\nNewsletter Issue ID:",
    result.get(
        "newsletter_issue_id"
    )
    )    


if __name__ == "__main__":
    asyncio.run(main())