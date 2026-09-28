from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    research_mcp_url: str | None = None

    hf_token: str
    hf_model_id: str = "Qwen/Qwen3-8B"

    # "local" runs the embedding model in this process (needs
    # ~500MB+ free; fine locally, too much for some free hosts).
    # "hf" calls the same model via HF's free Inference API
    # instead — same vectors, no local memory cost.
    embeddings_provider: str = "local"

    # Only required if BREVO_API_KEY is unset (see get_email_provider).
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str

    # Used instead of SMTP when set (see get_email_provider).
    brevo_api_key: str | None = None

    GITHUB_TOKEN: str | None = None

    # Used for "read on the web" links in emails.
    frontend_url: str = "http://localhost:5173"

    # Public URL of this API; one-click unsubscribe (RFC 8058)
    # posts here straight from the mail client.
    api_url: str = "http://127.0.0.1:8000"

    # Built-in scheduler (runs inside the API process; use a
    # single worker when enabled).
    scheduler_enabled: bool = False
    ingest_every_hours: float = 6
    # 0 = Monday ... 6 = Sunday, in UTC
    compose_weekday: int = 6
    compose_hour_utc: int = 6
    # Off by default: a human reviews each draft first.
    auto_publish: bool = False

    # Pause between emails; Gmail SMTP throttles bursts.
    email_send_interval_seconds: float = 1.0

    # Free LLM providers (OpenAI-compatible). Any that have a
    # key are tried in order; see app/core/free_llm.py.
    groq_api_key: str | None = None
    cerebras_api_key: str | None = None
    gemini_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str | None = None

    # Optional explicit chains, e.g.
    # "groq:openai/gpt-oss-20b,hf:Qwen/Qwen3-8B"
    llm_fast_chain: str | None = None
    llm_strong_chain: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()