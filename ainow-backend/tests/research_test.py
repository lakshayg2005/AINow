def main():
    from app.db.database import SessionLocal
    from app.schemas.research import ResearchCandidate
    from app.services.research import check_source_freshness

    # This file tests the freshness engine (services/research.py)

    db = SessionLocal()

    try:
        # For testing semantic duplicate detection
        candidate = ResearchCandidate(
            title="Quantum Hardware Could Speed Up Machine Learning",
            url="https://fresh-example.com/another-quantum-story",
            source_name="Fresh News",
            category="research",
            raw_content=(
                "Scientists are developing quantum computing hardware "
                "that could accelerate artificial intelligence and "
                "machine learning workloads."
            ),
        )

        result = check_source_freshness(
            candidate,
            db,
        )

        print(result.model_dump())

    finally:
        db.close()


if __name__ == "__main__":
    main()