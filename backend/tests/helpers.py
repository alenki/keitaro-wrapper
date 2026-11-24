import os

from app.config import Settings

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://wrapper:wrapper@127.0.0.1:5432/keitaro_wrapper_test",
)


def make_settings(**overrides) -> Settings:
    values = {
        "database_url": TEST_DATABASE_URL,
        "keitaro_url": "http://keitaro.test",
        "keitaro_api_key": "test-key",
        "campaign_prefix": "test_karaf_",
        # INFO, so every log call in the code really builds a record during tests
        "log_level": "INFO",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)
