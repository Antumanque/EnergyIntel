"""
Configuration management using pydantic-settings.

This module loads all configuration from environment variables and provides
type-safe access to settings throughout the application.
"""

import os
from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings can be overridden via environment variables or a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database configuration
    db_host: str = Field(
        default="localhost",
        description="Database host (use 'api_db' for Docker Compose service)",
    )
    db_port: int = Field(default=3306, description="Database port")
    db_user: str = Field(default="api_user", description="Database username")
    db_password: str = Field(default="api_password", description="Database password")
    db_name: str = Field(
        default="api_ingestion", description="Database name"
    )

    # API configuration
    api_urls: List[str] = Field(
        default_factory=list,
        description="List of API URLs to fetch (use API_URL_1, API_URL_2, etc.)",
    )

    # HTTP client configuration
    request_timeout: int = Field(
        default=30, description="HTTP request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, description="Maximum number of retry attempts for failed requests"
    )

    @field_validator("api_urls", mode="before")
    @classmethod
    def parse_api_urls(cls, v: str | List[str]) -> List[str]:
        """
        Parse API URLs from numbered environment variables.

        Looks for API_URL_1, API_URL_2, API_URL_3, etc. in the environment.
        Also supports comma-separated string for backward compatibility.

        Args:
            v: Either a comma-separated string or a list of URLs

        Returns:
            List of URL strings with whitespace stripped
        """
        # First, try to load from numbered environment variables
        urls = []
        i = 1
        while True:
            url = os.getenv(f"API_URL_{i}")
            if url:
                urls.append(url.strip())
                i += 1
            else:
                break

        # If we found numbered URLs, return those
        if urls:
            return urls

        # Otherwise, fall back to parsing the value passed in
        if isinstance(v, str):
            # Split by comma and strip whitespace
            urls = [url.strip() for url in v.split(",") if url.strip()]
            return urls
        return v if v else []

    @property
    def database_url(self) -> str:
        """
        Generate a database connection URL.

        Returns:
            MySQL connection string
        """
        return (
            f"mysql+mysqlconnector://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def get_db_config(self) -> dict:
        """
        Get database configuration as a dictionary for mysql.connector.

        Returns:
            Dictionary with database connection parameters
        """
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
        }


# Singleton instance
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Get the application settings singleton.

    This ensures settings are loaded only once and reused throughout the application.

    Returns:
        Settings instance with all configuration loaded
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
