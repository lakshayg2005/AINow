from app.db.database import SessionLocal
from app.schemas.research import ResearchCandidate
from app.services.research import check_source_freshness

#   This Files Test the Freshness Engine(services/reserach.py) of Research Module

db = SessionLocal()

# candidate = ResearchCandidate(
#     title="A completely new AI development",
#     url="https://fresh-example.com/new-ai-story",
#     source_name="Fresh News",
#     raw_content=(
#         "Researchers have announced an unrelated breakthrough "
#         "in artificial intelligence for scientific computing."
#     ),
# )
#For Testing semantic Duplicate
candidate = ResearchCandidate(
    title="Quantum Hardware Could Speed Up Machine Learning",
    url="https://fresh-example.com/another-quantum-story",
    source_name="Fresh News",
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

db.close()