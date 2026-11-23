from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    APP_NAME: str = "Corneoscope"
    MAX_UPLOAD_MB: int = 15
    MAX_PAGES: int = 100
    API_KEY: SecretStr = Field(min_length=32)


settings = Settings()
