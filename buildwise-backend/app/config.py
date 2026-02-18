"""BuildWise configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://buildwise:buildwise_dev@localhost:5432/buildwise"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth0
    auth0_domain: str = ""
    auth0_api_audience: str = ""
    auth0_algorithms: list[str] = ["RS256"]

    # GCS
    gcs_bucket_name: str = "buildwise-files"
    gcs_weather_bucket: str = "buildwise-weather"

    # EnergyPlus
    energyplus_image: str = "nrel/energyplus:24.1.0"
    energyplus_timeout_seconds: int = 3600

    # Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # App
    debug: bool = False
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
