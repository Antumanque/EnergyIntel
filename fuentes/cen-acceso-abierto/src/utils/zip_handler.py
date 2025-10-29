"""
Utilidad para manejar archivos .zip que contienen formularios.

Descomprime archivos .zip y busca formularios SUCTD, SAC o Fehaciente
dentro de ellos.
"""

import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class ZipFormularioHandler:
    """Maneja descompresión y extracción de formularios desde archivos .zip."""

    # Patrones para identificar formularios
    SUCTD_PATTERNS = [
        r'suctd',
        r'suct[_\s]',
        r'formulario.*suctd',
        r'solicitud.*uso.*capacidad'
    ]

    SAC_PATTERNS = [
        r'sac[_\s\.]',
        r'formulario.*sac',
        r'solicitud.*acceso.*conexion'
    ]

    FEHACIENTE_PATTERNS = [
        r'fehaciente',
        r'proyecto.*fehaciente',
        r'formulario.*fehaciente'
    ]

    def __init__(self):
        """Inicializa el manejador de ZIPs."""
        self.temp_dir = None

    def extract_zip(self, zip_path: str) -> str:
        """
        Extrae un archivo .zip en una carpeta temporal.

        Args:
            zip_path: Ruta al archivo .zip

        Returns:
            Ruta a la carpeta temporal con archivos extraídos

        Raises:
            ValueError: Si el archivo no es un ZIP válido
        """
        zip_path = Path(zip_path)

        if not zip_path.exists():
            raise ValueError(f"Archivo no encontrado: {zip_path}")

        if not zipfile.is_zipfile(zip_path):
            raise ValueError(f"No es un archivo ZIP válido: {zip_path}")

        # Crear carpeta temporal
        self.temp_dir = tempfile.mkdtemp(prefix="formulario_zip_")
        logger.info(f"📦 Extrayendo ZIP a: {self.temp_dir}")

        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(self.temp_dir)
                extracted_files = zip_ref.namelist()
                logger.info(f"✅ Extraídos {len(extracted_files)} archivos")

            return self.temp_dir

        except Exception as e:
            # Limpiar si falla
            self.cleanup()
            raise ValueError(f"Error al extraer ZIP: {e}")

    def find_formulario(
        self,
        extracted_dir: str,
        tipo_formulario: str = 'SUCTD'
    ) -> Optional[Tuple[str, str]]:
        """
        Busca un formulario específico en los archivos extraídos.

        Args:
            extracted_dir: Directorio con archivos extraídos
            tipo_formulario: 'SUCTD', 'SAC' o 'FEHACIENTE'

        Returns:
            Tupla (ruta_archivo, formato) o None si no encuentra

        Busca recursivamente archivos .pdf, .xlsx, .xls que coincidan
        con los patrones del tipo de formulario.
        """
        # Seleccionar patrones según tipo
        if tipo_formulario == 'SUCTD':
            patterns = self.SUCTD_PATTERNS
        elif tipo_formulario == 'SAC':
            patterns = self.SAC_PATTERNS
        elif tipo_formulario == 'FEHACIENTE':
            patterns = self.FEHACIENTE_PATTERNS
        else:
            raise ValueError(f"Tipo de formulario no soportado: {tipo_formulario}")

        # Buscar archivos recursivamente
        extracted_path = Path(extracted_dir)
        valid_extensions = ['.pdf', '.xlsx', '.xls']

        found_files = []

        for ext in valid_extensions:
            for file_path in extracted_path.rglob(f'*{ext}'):
                file_name = file_path.name.lower()

                # Verificar si coincide con algún patrón
                for pattern in patterns:
                    if re.search(pattern, file_name, re.IGNORECASE):
                        formato = ext.upper().replace('.', '')
                        found_files.append((str(file_path), formato, file_path.stat().st_size))
                        logger.info(f"✅ Encontrado: {file_path.name} ({formato})")
                        break

        if not found_files:
            logger.warning(f"⚠️  No se encontró formulario {tipo_formulario} en el ZIP")
            return None

        # Si hay múltiples, priorizar:
        # 1. PDF sobre XLSX
        # 2. Archivo más grande (probablemente el firmado/completo)
        found_files.sort(key=lambda x: (
            0 if x[1] == 'PDF' else 1,  # PDF primero
            -x[2]  # Más grande primero
        ))

        selected_file, selected_formato, selected_size = found_files[0]

        if len(found_files) > 1:
            logger.info(
                f"📋 Encontrados {len(found_files)} archivos, "
                f"seleccionando: {Path(selected_file).name}"
            )

        return (selected_file, selected_formato)

    def cleanup(self):
        """Elimina la carpeta temporal creada."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.info(f"🧹 Carpeta temporal eliminada: {self.temp_dir}")
                self.temp_dir = None
            except Exception as e:
                logger.warning(f"⚠️  No se pudo eliminar carpeta temporal: {e}")

    def process_zip_formulario(
        self,
        zip_path: str,
        tipo_formulario: str = 'SUCTD'
    ) -> Optional[Tuple[str, str]]:
        """
        Procesa un archivo .zip completo: extrae, busca y retorna formulario.

        Args:
            zip_path: Ruta al archivo .zip
            tipo_formulario: 'SUCTD', 'SAC' o 'FEHACIENTE'

        Returns:
            Tupla (ruta_temporal_archivo, formato) o None si no encuentra

        IMPORTANTE: El archivo retornado está en una carpeta temporal.
        Debe ser procesado inmediatamente y luego llamar a cleanup().
        """
        try:
            # Paso 1: Extraer ZIP
            extracted_dir = self.extract_zip(zip_path)

            # Paso 2: Buscar formulario
            result = self.find_formulario(extracted_dir, tipo_formulario)

            if result is None:
                self.cleanup()

            return result

        except Exception as e:
            logger.error(f"❌ Error al procesar ZIP: {e}")
            self.cleanup()
            return None


def get_formulario_from_zip(
    zip_path: str,
    tipo_formulario: str = 'SUCTD'
) -> Optional[Tuple[str, str, ZipFormularioHandler]]:
    """
    Función helper para obtener un formulario desde un ZIP.

    Args:
        zip_path: Ruta al archivo .zip
        tipo_formulario: 'SUCTD', 'SAC' o 'FEHACIENTE'

    Returns:
        Tupla (ruta_archivo, formato, handler) o None

    IMPORTANTE: Debes llamar a handler.cleanup() después de usar el archivo.

    Ejemplo:
        result = get_formulario_from_zip('path/to/file.zip', 'SUCTD')
        if result:
            file_path, formato, handler = result
            try:
                # Procesar archivo
                data = parse_suctd_pdf(file_path)
            finally:
                # Limpiar
                handler.cleanup()
    """
    handler = ZipFormularioHandler()
    result = handler.process_zip_formulario(zip_path, tipo_formulario)

    if result is None:
        return None

    file_path, formato = result
    return (file_path, formato, handler)
