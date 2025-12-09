"""
Schemas Pydantic para validación de datos de solicitudes y documentos del CEN.

Estos modelos validan que los datos de la API tengan la estructura esperada
y los tipos correctos antes de procesarlos.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class SolicitudAPI(BaseModel):
    """
    Schema para una solicitud tal como viene de la API del CEN.

    Campos requeridos: id, tipo_solicitud_id
    """
    # Campos requeridos
    id: int = Field(..., description="ID único de la solicitud")
    tipo_solicitud_id: int = Field(..., description="ID del tipo de solicitud")

    # Campos importantes
    tipo_solicitud: Optional[str] = None
    estado_solicitud_id: Optional[int] = None
    estado_solicitud: Optional[str] = None
    proyecto: Optional[str] = None
    proyecto_id: Optional[int] = None

    # Ubicación
    region_id: Optional[int] = None
    region: Optional[str] = None
    provincia_id: Optional[int] = None
    provincia: Optional[str] = None
    comuna_id: Optional[int] = None
    comuna: Optional[str] = None
    lat: Optional[str] = None
    lng: Optional[str] = None

    # Empresa
    razon_social: Optional[str] = None
    rut_empresa: Optional[str] = None
    rut_solicitante: Optional[str] = None
    empresa_solicitante: Optional[str] = None

    # Técnico
    nombre_se: Optional[str] = None
    nivel_tension: Optional[int] = None
    seccion_barra_conexion: Optional[str] = None
    pano_conexion: Optional[str] = None
    potencia_nominal: Optional[str] = None
    tipo_tecnologia_nombre: Optional[str] = None
    calificacion_id: Optional[int] = None
    calificacion_nombre: Optional[str] = None

    # Fechas
    create_date: Optional[str] = None
    update_date: Optional[str] = None
    fecha_estimada_conexion: Optional[str] = None
    fecha_informe: Optional[str] = None
    cancelled_at: Optional[str] = None
    deleted_at: Optional[str] = None

    # Etapa
    etapa_id: Optional[int] = None
    etapa: Optional[str] = None

    # Otros
    nup: Optional[str] = None
    cup: Optional[str] = None
    re_ordinal: Optional[str] = None
    last_prorroga_dec_const: Optional[str] = None
    plazo_dec_en_const: Optional[str] = None
    informe_fechaciente: Optional[str] = None

    class Config:
        extra = "allow"  # Permitir campos extra

    @field_validator('id', 'tipo_solicitud_id', mode='before')
    @classmethod
    def parse_required_int(cls, v):
        """Asegurar que los campos requeridos sean int."""
        if v is None:
            raise ValueError("Campo requerido")
        return int(v)


class DocumentoAPI(BaseModel):
    """
    Schema para un documento tal como viene de la API del CEN.

    Campos requeridos: id, solicitud_id, tipo_documento
    """
    # Campos requeridos
    id: int = Field(..., description="ID único del documento")
    solicitud_id: int = Field(..., description="ID de la solicitud padre")
    tipo_documento: str = Field(..., description="Tipo de documento")

    # Campos importantes
    nombre: Optional[str] = None
    ruta_s3: Optional[str] = None
    tipo_documento_id: Optional[int] = None

    # Metadata
    create_date: Optional[str] = None
    update_date: Optional[str] = None
    deleted: Optional[int] = None
    visible: Optional[int] = None

    # Empresa
    empresa_id: Optional[str] = None
    razon_social: Optional[str] = None

    # Estado
    estado_solicitud_id: Optional[str] = None
    etapa_id: Optional[int] = None
    etapa: Optional[str] = None

    # Otros
    version_id: Optional[str] = None
    user_management_id: Optional[Any] = None
    garantia: Optional[Any] = None

    class Config:
        extra = "allow"  # Permitir campos extra

    @field_validator('id', 'solicitud_id', mode='before')
    @classmethod
    def parse_required_int(cls, v):
        """Asegurar que los campos requeridos sean int."""
        if v is None:
            raise ValueError("Campo requerido")
        return int(v)

    @field_validator('tipo_documento', mode='before')
    @classmethod
    def parse_tipo_documento(cls, v):
        """Asegurar que tipo_documento sea string."""
        if v is None or v == "":
            raise ValueError("tipo_documento es requerido")
        return str(v)


def validate_solicitud(solicitud_raw: dict) -> tuple[bool, Optional[SolicitudAPI], Optional[str]]:
    """
    Validar una solicitud contra el schema.

    Args:
        solicitud_raw: Diccionario con datos crudos de la solicitud

    Returns:
        Tupla (is_valid, solicitud_validada, error_message)
    """
    try:
        solicitud = SolicitudAPI.model_validate(solicitud_raw)
        return True, solicitud, None
    except Exception as e:
        return False, None, str(e)


def validate_documento(documento_raw: dict) -> tuple[bool, Optional[DocumentoAPI], Optional[str]]:
    """
    Validar un documento contra el schema.

    Args:
        documento_raw: Diccionario con datos crudos del documento

    Returns:
        Tupla (is_valid, documento_validado, error_message)
    """
    try:
        documento = DocumentoAPI.model_validate(documento_raw)
        return True, documento, None
    except Exception as e:
        return False, None, str(e)
