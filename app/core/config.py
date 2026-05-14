from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://watchdog:watchdog@localhost:5433/watchdog"
    test_database_url: str = "postgresql+asyncpg://watchdog:watchdog@localhost:5433/watchdog_test"

    # Security
    secret_key: str = "dev-secret-key-change-in-production"
    api_key_header: str = "X-API-Key"
    bootstrap_api_keys: str = "dev-key-1234"

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Anomaly detection
    anomaly_window_minutes: int = 5
    anomaly_lookback_windows: int = 6
    anomaly_zscore_threshold: float = 3.0
    alert_cooldown_minutes: int = 10

    # Webhook
    webhook_url: str = "http://webhook-receiver:9000/hook"
    webhook_type: str = "watchdog"   # watchdog | slack | generic
    webhook_receiver_url: str = "http://webhook-receiver:9000"

    # Dashboard
    dashboard_refresh_seconds: int = 10

    @property
    def api_keys(self) -> List[str]:
        return [k.strip() for k in self.bootstrap_api_keys.split(",") if k.strip()]

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
