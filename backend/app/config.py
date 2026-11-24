import re
from functools import lru_cache
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PREFIX_PATTERN = re.compile(r"^test_[a-z0-9]+_$")


class Settings(BaseSettings):
    """App configuration, read from environment variables with the same names."""

    model_config = SettingsConfigDict(env_file=("../.env", ".env"), extra="ignore")

    database_url: str
    keitaro_url: str = "https://keitaro-for-tests.etolegko.com"
    keitaro_api_key: SecretStr
    keitaro_timeout_seconds: float = 10.0
    # Path of a campaign page in the Keitaro admin, {id} is replaced with the campaign id
    keitaro_campaign_link: str = "/admin/#!/campaign/{id}/main"
    campaign_prefix: str = "test_karaf_"
    catalog_ttl_seconds: int = 300
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # Built frontend; by default backend/static, which exists only in the Docker image
    static_dir: str | None = None

    @field_validator("database_url")
    @classmethod
    def _require_asyncpg(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("must start with postgresql+asyncpg://")
        return value

    @field_validator("keitaro_url")
    @classmethod
    def _normalize_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("must be an http(s) URL")
        return value.rstrip("/")

    @field_validator("keitaro_campaign_link")
    @classmethod
    def _require_id_placeholder(cls, value: str) -> str:
        if "{id}" not in value:
            raise ValueError("must contain {id}")
        return value

    @field_validator("campaign_prefix")
    @classmethod
    def _check_prefix(cls, value: str) -> str:
        if not PREFIX_PATTERN.match(value):
            raise ValueError("must look like test_<surname>_")
        return value

    def campaign_url(self, campaign_id: int) -> str:
        return self.keitaro_url + self.keitaro_campaign_link.format(id=campaign_id)


@lru_cache
def get_settings() -> Settings:
    return Settings()
