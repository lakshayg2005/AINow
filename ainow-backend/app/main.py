from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine
from app.db import models
from app.routes.auth import router as auth_router
from app.routes.subscriptions import router as subscription_router
from app.routes.newsletters import router as newsletter_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="AINow API",
    description="Backend API for AINow AI Newsletter",
    version="1.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(subscription_router)
app.include_router(newsletter_router)

@app.get("/")
def root():
    return {
        "message": "AINow API is running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }