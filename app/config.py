from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App configuration, loaded from environment / .env.

    Provider secrets default to empty so the app can boot before every
    integration is configured; a provider is simply 'not connected' until
    its client id is present.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Core
    database_url: str = "sqlite:///./agent.db"
    token_encryption_key: str = ""
    anthropic_api_key: str = ""
    base_url: str = "http://localhost:8000"

    # Xero
    xero_client_id: str = ""
    xero_client_secret: str = ""
    xero_redirect_uri: str = "http://localhost:8000/auth/xero/callback"

    # Etsy
    etsy_api_key: str = ""
    etsy_shared_secret: str = ""
    etsy_redirect_uri: str = "http://localhost:8000/auth/etsy/callback"

    # Gmail
    gmail_client_id: str = ""
    gmail_client_secret: str = ""
    gmail_redirect_uri: str = "http://localhost:8000/auth/gmail/callback"

    # Dropbox
    dropbox_app_key: str = ""
    dropbox_app_secret: str = ""
    dropbox_redirect_uri: str = "http://localhost:8000/auth/dropbox/callback"

    # RevenueCat (app subscription revenue — webhook + REST API, not OAuth)
    revenuecat_api_key: str = ""  # secret REST API key (Bearer)
    revenuecat_webhook_authorization: str = ""  # shared secret to verify webhooks


@lru_cache
def get_settings() -> Settings:
    return Settings()
