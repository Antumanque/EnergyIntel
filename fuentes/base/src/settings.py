"""
Configuración de la aplicación usando pydantic-settings.

Este módulo carga toda la configuración desde variables de entorno y provee
acceso type-safe a settings a través de la aplicación.
"""

import os
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Settings de la aplicación cargados desde variables de entorno.

    Todos los settings pueden ser sobreescritos via variables de entorno o archivo .env.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # =============================================================================
    # CONFIGURACIÓN DE BASE DE DATOS
    # =============================================================================
    db_host: str = Field(
        default="localhost",
        description="Database host (usar 'base_db' para Docker Compose)",
    )
    db_port: int = Field(default=3306, description="Puerto de la base de datos")
    db_user: str = Field(default="base_user", description="Usuario de la base de datos")
    db_password: str = Field(
        default="base_password", description="Contraseña de la base de datos"
    )
    db_name: str = Field(default="fuentes_base", description="Nombre de la base de datos")

    # =============================================================================
    # CONFIGURACIÓN DE HTTP CLIENT
    # =============================================================================
    request_timeout: int = Field(
        default=30, description="Timeout de request HTTP en segundos"
    )
    max_retries: int = Field(
        default=3, description="Número máximo de intentos de retry para requests fallidos"
    )

    # =============================================================================
    # CONFIGURACIÓN DE TIPO DE FUENTE
    # =============================================================================
    source_type: Literal["api_rest", "web_static", "web_dynamic", "file_download"] | None = (
        Field(
            default=None,
            description="Tipo de fuente: api_rest, web_static, web_dynamic, file_download",
        )
    )

    # =============================================================================
    # CONFIGURACIÓN DE URLs (API, WEB, FILES)
    # =============================================================================
    api_urls: list[str] = Field(
        default_factory=list,
        description="Lista de URLs de API REST (usar API_URL_1, API_URL_2, etc.)",
    )

    web_urls: list[str] = Field(
        default_factory=list,
        description="Lista de URLs web para scraping (usar WEB_URL_1, WEB_URL_2, etc.)",
    )

    file_urls: list[str] = Field(
        default_factory=list,
        description="Lista de URLs de archivos (usar FILE_URL_1, FILE_URL_2, etc.)",
    )

    # =============================================================================
    # CONFIGURACIÓN DE PLAYWRIGHT (scraping dinámico)
    # =============================================================================
    playwright_headless: bool = Field(
        default=True, description="Ejecutar Playwright en modo headless"
    )
    playwright_slow_mo: int = Field(
        default=0, description="Slow motion en ms para debugging de Playwright"
    )
    playwright_timeout: int = Field(
        default=30000, description="Timeout de Playwright en ms"
    )

    # =============================================================================
    # CONFIGURACIÓN DE PARSERS
    # =============================================================================
    auto_parse: bool = Field(
        default=True, description="Habilitar parseo automático de archivos descargados"
    )
    parser_types: list[str] = Field(
        default_factory=lambda: ["pdf", "xlsx", "csv"],
        description="Tipos de parsers a habilitar",
    )

    # =============================================================================
    # CONFIGURACIÓN DE LOGGING
    # =============================================================================
    log_level: str = Field(default="INFO", description="Nivel de logging")
    log_file: str | None = Field(
        default=None, description="Ruta de archivo de log (opcional)"
    )

    # =============================================================================
    # CONFIGURACIÓN DE DOWNLOADS
    # =============================================================================
    download_dir: str = Field(
        default="downloads", description="Directorio para archivos descargados"
    )

    @field_validator("api_urls", mode="before")
    @classmethod
    def parse_api_urls(cls, v: str | list[str]) -> list[str]:
        """
        Parse API URLs desde variables de entorno numeradas.

        Busca API_URL_1, API_URL_2, API_URL_3, etc. en el environment.

        Args:
            v: String separado por comas o lista de URLs

        Returns:
            Lista de strings de URLs con whitespace stripped
        """
        return cls._parse_numbered_urls(v, "API_URL")

    @field_validator("web_urls", mode="before")
    @classmethod
    def parse_web_urls(cls, v: str | list[str]) -> list[str]:
        """Parse WEB URLs desde variables de entorno numeradas."""
        return cls._parse_numbered_urls(v, "WEB_URL")

    @field_validator("file_urls", mode="before")
    @classmethod
    def parse_file_urls(cls, v: str | list[str]) -> list[str]:
        """Parse FILE URLs desde variables de entorno numeradas."""
        return cls._parse_numbered_urls(v, "FILE_URL")

    @staticmethod
    def _parse_numbered_urls(v: str | list[str], prefix: str) -> list[str]:
        """
        Helper para parsear URLs numeradas desde env vars.

        Args:
            v: Valor a parsear
            prefix: Prefijo de la env var (ej. 'API_URL', 'WEB_URL')

        Returns:
            Lista de URLs
        """
        # Primero, intentar cargar desde variables de entorno numeradas
        urls = []
        i = 1
        while True:
            url = os.getenv(f"{prefix}_{i}")
            if url:
                urls.append(url.strip())
                i += 1
            else:
                break

        # Si encontramos URLs numeradas, retornar esas
        if urls:
            return urls

        # Sino, fallback a parsear el valor pasado
        if isinstance(v, str):
            # Dividir por coma y strip whitespace
            urls = [url.strip() for url in v.split(",") if url.strip()]
            return urls
        return v if v else []

    @field_validator("parser_types", mode="before")
    @classmethod
    def parse_parser_types(cls, v: str | list[str]) -> list[str]:
        """Parse parser types desde string separado por comas."""
        if isinstance(v, str):
            return [t.strip() for t in v.split(",") if t.strip()]
        return v if v else []

    @property
    def database_url(self) -> str:
        """
        Generar URL de conexión a la base de datos.

        Returns:
            MySQL connection string
        """
        return (
            f"mysql+mysqlconnector://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def get_db_config(self) -> dict:
        """
        Obtener configuración de base de datos como diccionario para mysql.connector.

        Returns:
            Diccionario con parámetros de conexión a la base de datos
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
    Obtener singleton de settings de la aplicación.

    Esto asegura que los settings se cargan solo una vez y se reusan en la aplicación.

    Returns:
        Instancia de Settings con toda la configuración cargada
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
