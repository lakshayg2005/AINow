from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    research_mcp_url: str | None = None

    hf_token: str
    hf_model_id: str = "Qwen/Qwen3-8B"

    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 465
    smtp_username: str
    smtp_password: str
    email_from: str

    GITHUB_TOKEN: str | None = None

    class Config:
        env_file = ".env"


settings = Settings()