from datetime import UTC, datetime
from typing import Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(hide_input_in_errors=True)

    database_url: str = Field(min_length=1, repr=False)


class ApiSettings(DatabaseSettings):
    api_key: SecretStr = Field(min_length=1)


class ConsumerSettings(DatabaseSettings):
    rabbitmq_url: str = Field(min_length=1, repr=False)
    webhook_max_attempts: int = Field(default=3, ge=1)
    webhook_retry_base_delay_seconds: int = Field(default=1, ge=1)

    @model_validator(mode="after")
    def validate_webhook_retry_schedule(self) -> Self:
        total_delay = self.webhook_retry_base_delay_seconds * (
            2 ** (self.webhook_max_attempts - 1) - 1
        )
        remaining_time = datetime.max.replace(tzinfo=UTC) - datetime.now(UTC)
        if total_delay >= remaining_time.total_seconds():
            raise ValueError(
                "Webhook retry schedule exceeds the supported timestamp range"
            )
        return self
