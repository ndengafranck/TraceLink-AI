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
    # Meta Model API (OpenAI-compatible). Empty key = AI disabled; the explanation
    # endpoint then returns the deterministic fallback. The key lives only in .env.
    model_api_key: str = ""
    model_base_url: str = "https://api.meta.ai/v1"
    model_name: str = "muse-spark-1.3"
    model_timeout_s: float = 30.0
    # Send a JSON-schema response_format. Turn off if the provider rejects it
    # (the answer is validated with Pydantic either way).
    model_structured_output: bool = True
    explain_per_hour: int = 10
    # Bluetooth sighting reports accepted per finder account per hour.
    reports_per_hour: int = 120


@lru_cache
def get_settings() -> Settings:
    return Settings()
