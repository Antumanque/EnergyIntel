"""
Schemas Pydantic para validación de datos de proyectos del SEA.

Estos modelos validan que los datos de la API tengan la estructura esperada
y los tipos correctos antes de procesarlos.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class LinkMapa(BaseModel):
    """Schema para el objeto LINK_MAPA."""
    SHOW: Optional[str] = None
    URL: Optional[str] = None
    IMAGE: Optional[str] = None


class ProyectoAPI(BaseModel):
    """
    Schema para un proyecto tal como viene de la API del SEA.

    Campos requeridos: EXPEDIENTE_ID, EXPEDIENTE_NOMBRE
    Resto de campos son opcionales.
    """
    # Campos requeridos
    EXPEDIENTE_ID: int = Field(..., description="ID único del expediente")
    EXPEDIENTE_NOMBRE: str = Field(..., description="Nombre del proyecto")

    # Campos opcionales
    EXPEDIENTE_URL_PPAL: Optional[str] = None
    EXPEDIENTE_URL_FICHA: Optional[str] = None
    WORKFLOW_DESCRIPCION: Optional[str] = None
    REGION_NOMBRE: Optional[str] = None
    COMUNA_NOMBRE: Optional[str] = None
    TIPO_PROYECTO: Optional[str] = None
    DESCRIPCION_TIPOLOGIA: Optional[str] = None
    RAZON_INGRESO: Optional[str] = None
    TITULAR: Optional[str] = None
    INVERSION_MM: Optional[float] = None
    INVERSION_MM_FORMAT: Optional[str] = None
    FECHA_PRESENTACION: Optional[int] = None
    FECHA_PRESENTACION_FORMAT: Optional[str] = None
    FECHA_PLAZO: Optional[int] = None
    FECHA_PLAZO_FORMAT: Optional[str] = None
    ESTADO_PROYECTO: Optional[str] = None
    ENCARGADO: Optional[str] = None
    ACTIVIDAD_ACTUAL: Optional[str] = None
    ETAPA: Optional[str] = None
    LINK_MAPA: Optional[Any] = None  # Puede ser dict o string JSON
    ACCIONES: Optional[str] = None
    DIAS_LEGALES: Optional[int] = None
    SUSPENDIDO: Optional[str] = None
    VER_ACTIVIDAD: Optional[str] = None

    class Config:
        extra = "allow"  # Permitir campos extra que no conocemos

    @field_validator('EXPEDIENTE_ID', mode='before')
    @classmethod
    def parse_expediente_id(cls, v):
        """Convertir a int si viene como string."""
        if v is None:
            raise ValueError("EXPEDIENTE_ID es requerido")
        return int(v)

    @field_validator('INVERSION_MM', mode='before')
    @classmethod
    def parse_inversion(cls, v):
        """Convertir inversión a float."""
        if v is None or v == "":
            return None
        try:
            return float(v)
        except (ValueError, TypeError):
            return None

    @field_validator('FECHA_PRESENTACION', 'FECHA_PLAZO', 'DIAS_LEGALES', mode='before')
    @classmethod
    def parse_int_fields(cls, v):
        """Convertir campos numéricos a int."""
        if v is None or v == "":
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None


class APIResponse(BaseModel):
    """Schema para la respuesta completa de la API."""
    status: bool = Field(..., description="Estado de la respuesta")
    totalRegistros: Optional[str] = None
    recordsTotal: Optional[Any] = None  # Puede ser int o string
    data: list[dict[str, Any]] = Field(default_factory=list)

    @field_validator('recordsTotal', mode='before')
    @classmethod
    def parse_records_total(cls, v):
        """Normalizar recordsTotal."""
        if v is None:
            return None
        return int(v) if isinstance(v, str) else v


def validate_proyecto(proyecto_raw: dict) -> tuple[bool, Optional[ProyectoAPI], Optional[str]]:
    """
    Validar un proyecto contra el schema.

    Args:
        proyecto_raw: Diccionario con datos crudos del proyecto

    Returns:
        Tupla (is_valid, proyecto_validado, error_message)
    """
    try:
        proyecto = ProyectoAPI.model_validate(proyecto_raw)
        return True, proyecto, None
    except Exception as e:
        return False, None, str(e)


def validate_api_response(response_data: dict) -> tuple[bool, Optional[APIResponse], Optional[str]]:
    """
    Validar una respuesta de la API contra el schema.

    Args:
        response_data: Diccionario con respuesta de la API

    Returns:
        Tupla (is_valid, response_validada, error_message)
    """
    try:
        response = APIResponse.model_validate(response_data)
        return True, response, None
    except Exception as e:
        return False, None, str(e)
