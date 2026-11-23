"""Server settings, read from env vars / .env (gitignored)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    litedrive_fake_supabase: bool = False
    supabase_url: str = ""
    supabase_publishable_key: str = ""  # sb_publishable_... (client-facing calls: sign-in, /auth/v1/user)
    supabase_secret_key: str = ""  # sb_secret_... (server-side only: PostgREST, Storage, admin)
    supabase_bucket: str = "drive"
    signed_url_ttl_seconds: int = 300


@lru_cache
def get_settings() -> Settings:
    return Settings()
