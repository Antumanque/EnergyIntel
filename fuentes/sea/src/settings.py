"""
Configuración de la aplicación usando pydantic-settings.

Este módulo carga toda la configuración desde variables de entorno y provee
acceso type-safe a settings a través de la aplicación.
"""

from pydantic import Field
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
        description="Database host (usar 'sea_db' para Docker Compose)",
    )
    db_port: int = Field(default=3306, description="Puerto de la base de datos")
    db_user: str = Field(default="sea_user", description="Usuario de la base de datos")
    db_password: str = Field(
        default="sea_password", description="Contraseña de la base de datos"
    )
    db_name: str = Field(default="sea_seia", description="Nombre de la base de datos")

    # =============================================================================
    # CONFIGURACIÓN DE LA API DEL SEA
    # =============================================================================
    sea_api_base_url: str = Field(
        default="https://seia.sea.gob.cl/busqueda/buscarProyectoResumenAction.php",
        description="URL base de la API de búsqueda de proyectos del SEA",
    )

    # Parámetros de búsqueda
    sea_nombre: str = Field(default="", description="Filtro por nombre del proyecto")
    sea_titular: str = Field(default="", description="Filtro por titular del proyecto")
    sea_folio: str = Field(default="", description="Filtro por folio")
    sea_select_region: str = Field(default="", description="Filtro por región")
    sea_select_comuna: str = Field(default="", description="Filtro por comuna")
    sea_tipo_presentacion: str = Field(
        default="", description="Filtro por tipo de presentación (DIA, EIA)"
    )
    sea_project_status: str = Field(default="", description="Filtro por estado del proyecto")
    sea_presentacion_min: str = Field(
        default="", description="Fecha mínima de presentación (DD-MM-YYYY)"
    )
    sea_presentacion_max: str = Field(
        default="", description="Fecha máxima de presentación (DD-MM-YYYY)"
    )
    sea_califica_min: str = Field(
        default="", description="Fecha mínima de calificación (DD-MM-YYYY)"
    )
    sea_califica_max: str = Field(
        default="", description="Fecha máxima de calificación (DD-MM-YYYY)"
    )
    sea_sectores_economicos: str = Field(
        default="", description="Filtro por sectores económicos"
    )
    sea_razon_ingreso: str = Field(default="", description="Filtro por razón de ingreso")
    sea_id_tipo_expediente: str = Field(
        default="", description="Filtro por ID de tipo de expediente"
    )

    # Paginación y ordenamiento
    sea_limit: int = Field(default=100, description="Número de resultados por página")
    sea_order_column: str = Field(
        default="FECHA_PRESENTACION", description="Columna para ordenar resultados"
    )
    sea_order_dir: str = Field(
        default="desc", description="Dirección de ordenamiento (asc/desc)"
    )

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
    # CONFIGURACIÓN DE LOGGING
    # =============================================================================
    log_level: str = Field(default="INFO", description="Nivel de logging")
    log_file: str | None = Field(
        default=None, description="Ruta de archivo de log (opcional)"
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

    def build_api_params(self, offset: int = 1) -> dict:
        """
        Construir parámetros para la API del SEA.

        Args:
            offset: Offset de paginación (página)

        Returns:
            Diccionario con todos los parámetros de la API
        """
        return {
            "nombre": self.sea_nombre,
            "titular": self.sea_titular,
            "folio": self.sea_folio,
            "selectRegion": self.sea_select_region,
            "selectComuna": self.sea_select_comuna,
            "tipoPresentacion": self.sea_tipo_presentacion,
            "projectStatus": self.sea_project_status,
            "PresentacionMin": self.sea_presentacion_min,
            "PresentacionMax": self.sea_presentacion_max,
            "CalificaMin": self.sea_califica_min,
            "CalificaMax": self.sea_califica_max,
            "sectores_economicos": self.sea_sectores_economicos,
            "razoningreso": self.sea_razon_ingreso,
            "id_tipoexpediente": self.sea_id_tipo_expediente,
            "offset": offset,
            "limit": self.sea_limit,
            "orderColumn": self.sea_order_column,
            "orderDir": self.sea_order_dir,
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
