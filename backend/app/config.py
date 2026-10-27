from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration read from environment variables (or a local .env file).

    JWT_SECRET has no default on purpose: the app refuses to start without it,
    so a secret can never be silently committed to the repository.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./tracelink.db"
    jwt_secret: str
    # Fernet key (base64, 32 bytes) used to encrypt IMEIs at rest.
    imei_encryption_key: str
    # Separate secret for the keyed hash used to detect duplicate IMEIs.
    imei_hmac_key: str
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 30
    # When true, the ownership code is returned in the API response, standing in
    # for "the code shown on the phone". Off by default: with it off, the API
    # refuses to issue codes until a real delivery channel (the Android app) exists.
    demo_mode: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
