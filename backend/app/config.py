from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite+aiosqlite:///./surveyiq.db"
    SECRET_KEY: str = "supersecretkey"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    HF_API_KEY: str = ""
    HF_MODEL: str = "mistralai/Mistral-7B-Instruct-v0.3"
    MISTRAL_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    DEFAULT_AI_PROVIDER: str = "mistral"
    REPORT_WEBHOOK_URL: str = ""
    REPORT_DEFAULT_RECIPIENT: str = "survey-team"
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"
    ENABLE_DOCS: bool = True

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
