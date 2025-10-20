"""
Gestión de configuración usando pydantic-settings.

Este módulo carga toda la configuración de variables de entorno y provee
acceso type-safe a configuraciones en toda la aplicación.
"""

from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuraciones de aplicación cargadas desde variables de entorno.

    Todas las configuraciones pueden ser sobrescritas vía variables de entorno o archivo .env.
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
        description="Database host (use 'cen_db' for Docker Compose service)",
    )
    db_port: int = Field(default=3306, description="Database port")
    db_user: str = Field(default="cen_user", description="Database username")
    db_password: str = Field(default="cen_password", description="Database password")
    db_name: str = Field(
        default="cen_acceso_abierto", description="Database name"
    )

    # CEN API configuration (nueva configuración)
    cen_api_base_url: str = Field(
        default="https://pkb3ax2pkg.execute-api.us-east-2.amazonaws.com/prod/data/public",
        description="Base URL for CEN Public API",
    )
    cen_years: str = Field(
        default="2025",
        description="Years to fetch data for (comma-separated in .env)",
    )
    cen_document_types: str = Field(
        default="Formulario SUCTD,Formulario SAC,Formulario_proyecto_fehaciente",
        description="Document types to extract (exact strings from API)",
    )

    @property
    def cen_years_list(self) -> List[int]:
        """Parse cen_years string to list of ints."""
        if isinstance(self.cen_years, str):
            return [int(y.strip()) for y in self.cen_years.split(',') if y.strip()]
        return [2025]

    @property
    def cen_document_types_list(self) -> List[str]:
        """Parse cen_document_types string to list of strings."""
        if isinstance(self.cen_document_types, str):
            return [d.strip() for d in self.cen_document_types.split(',') if d.strip()]
        return ["Formulario SUCTD", "Formulario SAC", "Formulario_proyecto_fehaciente"]

    # HTTP client configuration
    request_timeout: int = Field(
        default=30, description="HTTP request timeout in seconds"
    )
    max_retries: int = Field(
        default=3, description="Maximum number of retry attempts for failed requests"
    )

    @property
    def database_url(self) -> str:
        """
        Genera una URL de conexión a la base de datos.
        """
        return (
            f"mysql+mysqlconnector://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    def get_db_config(self) -> dict:
        """
        Obtiene la configuración de base de datos como diccionario para mysql.connector.
        """
        return {
            "host": self.db_host,
            "port": self.db_port,
            "user": self.db_user,
            "password": self.db_password,
            "database": self.db_name,
        }


# Instancia singleton
_settings: Settings | None = None


def get_settings() -> Settings:
    """
    Obtiene el singleton de configuraciones de la aplicación.

    Esto asegura que las configuraciones se carguen una sola vez y se reutilicen en toda la aplicación.
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
