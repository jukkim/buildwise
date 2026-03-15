"""BuildWise configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database — override via DATABASE_URL env var or .env file for production
    database_url: str = "postgresql+asyncpg://buildwise:buildwise_dev@localhost:5432/buildwise"

    def model_post_init(self, __context: object) -> None:
        # Railway injects postgresql:// but asyncpg needs postgresql+asyncpg://
        if self.database_url.startswith("postgresql://"):
            object.__setattr__(self, "database_url", self.database_url.replace("postgresql://", "postgresql+asyncpg://", 1))
        elif self.database_url.startswith("postgres://"):
            object.__setattr__(self, "database_url", self.database_url.replace("postgres://", "postgresql+asyncpg://", 1))

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Auth0
    auth0_domain: str = ""
    auth0_api_audience: str = ""
    auth0_client_id: str = ""
    auth0_algorithms: list[str] = ["RS256"]

    # GCS
    gcs_bucket_name: str = "buildwise-files"
    gcs_weather_bucket: str = "buildwise-weather"

    # EnergyPlus
    energyplus_image: str = "nrel/energyplus:24.1.0"
    energyplus_timeout_seconds: int = 900

    # Simulation mode: "auto" (mock if debug else real), "mock", "real"
    simulation_mode: str = "auto"

    # Billing
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    # AI (Claude API for NL → BPS parsing)
    anthropic_api_key: str = ""

    # App
    debug: bool = False
    log_level: str = "INFO"

    # CORS
    cors_origins: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
