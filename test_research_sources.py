from app.research.orchestrator import collect_candidates


candidates = collect_candidates(
    limit_per_source=5,
)

print(
    f"Collected {len(candidates)} candidates"
)

for candidate in candidates[:10]:
    print()
    print("TITLE:", candidate.title)
    print("SOURCE:", candidate.source_name)
    print("URL:", candidate.url)