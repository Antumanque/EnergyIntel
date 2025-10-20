"""
Parser de Formularios SAC en formato PDF.

Este módulo extrae datos estructurados de formularios SAC (Solicitud de
Autorización de Conexión) usando pdfplumber para detectar y parsear tablas.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any
import pdfplumber

logger = logging.getLogger(__name__)


class SACPDFParser:
    """
    Parser para Formularios SAC en PDF.

    Los formularios SAC son PDFs generados desde Excel que contienen
    una tabla estructurada con ~32 filas.
    """

    def __init__(self):
        """Inicializa el parser de SAC."""
        self.version = "1.0.0"

    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parsea un formulario SAC desde PDF.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Diccionario con datos extraídos del formulario (incluye metadata del PDF)

        Raises:
            FileNotFoundError: Si el archivo no existe
            Exception: Si hay error al parsear
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {pdf_path}")

        logger.info(f"📄 Parseando formulario SAC: {pdf_file.name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Formularios SAC típicamente tienen 1 página
                if len(pdf.pages) == 0:
                    raise ValueError("PDF sin páginas")

                page = pdf.pages[0]

                # Extraer metadata del PDF
                metadata = pdf.metadata or {}
                pdf_metadata = {
                    'pdf_producer': metadata.get('Producer'),
                    'pdf_author': metadata.get('Author'),
                    'pdf_title': metadata.get('Title'),
                    'pdf_creation_date': self._parse_pdf_date(metadata.get('CreationDate')),
                }

                # Extraer tabla
                tables = page.extract_tables()
                if not tables:
                    raise ValueError("No se detectaron tablas en el PDF")

                table = tables[0]
                logger.debug(f"Tabla extraída: {len(table)} filas")

                # Parsear datos de la tabla
                data = self._parse_table(table)

                # Agregar metadata del PDF
                data.update(pdf_metadata)

                logger.info(f"✅ Formulario SAC parseado: {data.get('nombre_proyecto', 'N/A')}")
                return data

        except Exception as e:
            logger.error(f"❌ Error al parsear SAC: {str(e)}", exc_info=True)
            raise

    def _parse_table(self, table: list) -> Dict[str, Any]:
        """
        Parsea la tabla extraída del PDF.

        Args:
            table: Lista de filas (cada fila es una lista de celdas)

        Returns:
            Diccionario con datos estructurados
        """
        data = {}

        # Iterar sobre las filas buscando labels y valores
        for row in table:
            if not row or len(row) < 2:
                continue

            # Limpiar valores None
            clean_row = [str(cell).strip() if cell else "" for cell in row]

            # El patrón general es: columna[1] = label, columna[2+] = valor
            label = clean_row[1].lower() if len(clean_row) > 1 else ""
            value = clean_row[2] if len(clean_row) > 2 else ""

            # === SECCIÓN: Antecedentes Generales del Solicitante ===

            if "razón social" in label or "razon social" in label:
                data["razon_social"] = value

            elif label == "rut":
                data["rut"] = value

            elif label == "giro":
                data["giro"] = value

            elif "domicilio legal" in label:
                data["domicilio_legal"] = value

            # === SECCIÓN: Representante Legal ===

            elif "nombre del representante legal" in label:
                # El valor puede estar en columna[4] en lugar de [2]
                value = clean_row[4] if len(clean_row) > 4 and clean_row[4] else value
                data["representante_legal_nombre"] = value

            elif label == "e-mail" and "representante_legal_nombre" in data:
                # Primer email es del representante legal
                data["representante_legal_email"] = value
                # Teléfono en columna[7]
                if len(clean_row) > 7:
                    data["representante_legal_telefono"] = clean_row[7]

            # === SECCIÓN: Coordinadores de Proyecto ===

            elif "nombre coordinador de proyecto" in label:
                # Puede haber hasta 3 coordinadores
                coord_nombre = clean_row[4] if len(clean_row) > 4 and clean_row[4] else value

                # Determinar cuál coordinador es (1, 2 o 3)
                if "coordinador_proyecto_1_nombre" not in data:
                    data["coordinador_proyecto_1_nombre"] = coord_nombre
                    self._next_coord = 1
                elif "coordinador_proyecto_2_nombre" not in data:
                    data["coordinador_proyecto_2_nombre"] = coord_nombre
                    self._next_coord = 2
                elif "coordinador_proyecto_3_nombre" not in data:
                    data["coordinador_proyecto_3_nombre"] = coord_nombre
                    self._next_coord = 3

            elif label == "e-mail" and hasattr(self, '_next_coord'):
                # Email del último coordinador agregado
                coord_num = self._next_coord
                data[f"coordinador_proyecto_{coord_num}_email"] = value
                # Teléfono en columna[7]
                if len(clean_row) > 7:
                    data[f"coordinador_proyecto_{coord_num}_telefono"] = clean_row[7]

            # === SECCIÓN: Antecedentes del Proyecto ===

            elif "nombre del proyecto" in label:
                data["nombre_proyecto"] = clean_row[3] if len(clean_row) > 3 else value

            elif "tipo proyecto" in label:
                # Puede tener múltiples valores: Gen / Trans / Consumo
                data["tipo_proyecto"] = value

            elif "tecnología" in label or "tecnologia" in label:
                # Siguiente fila normalmente contiene el valor
                # Buscar en clean_row índices mayores
                tech_value = ""
                for i in range(2, len(clean_row)):
                    if clean_row[i] and clean_row[i] not in ["", "eólica", "hidro", "solar", "térmica", "otro"]:
                        tech_value = clean_row[i]
                        break
                data["tecnologia"] = tech_value

            elif "potencia nominal" in label:
                # Puede ser "400 + 100" o similar
                pot_value = clean_row[3] if len(clean_row) > 3 and clean_row[3] else value
                data["potencia_nominal_mw"] = pot_value

            elif "consumo propio" in label:
                value_str = clean_row[3] if len(clean_row) > 3 else value
                data["consumo_propio_mw"] = self._parse_decimal(value_str)

            elif "factor de potencia" in label:
                value_str = clean_row[4] if len(clean_row) > 4 else value
                data["factor_potencia"] = self._parse_decimal(value_str)

            # === SECCIÓN: Ubicación Geográfica del Proyecto ===

            elif "coordenadas u.t.m." in label.lower() and "proyecto" not in data.get("nombre_subestacion", ""):
                # Primera aparición de coordenadas = ubicación del proyecto
                if "proyecto_coordenadas_utm_huso" not in data:
                    # Huso en columna[3], Este en columna[5-6], Norte en columna[7-8]
                    if len(clean_row) > 3:
                        data["proyecto_coordenadas_utm_huso"] = clean_row[3] + " " + clean_row[4] if len(clean_row) > 4 else clean_row[3]
                    if len(clean_row) > 6:
                        data["proyecto_coordenadas_utm_este"] = clean_row[6]
                    if len(clean_row) > 8:
                        data["proyecto_coordenadas_utm_norte"] = clean_row[8]

            elif label == "comuna" and "proyecto_comuna" not in data:
                # Primera aparición de comuna = comuna del proyecto
                data["proyecto_comuna"] = value
                # Región típicamente está en columna[5-6]
                if len(clean_row) > 5 and "región" in clean_row[5].lower():
                    data["proyecto_region"] = clean_row[6] if len(clean_row) > 6 else ""

            # === SECCIÓN: Antecedentes del Punto de Conexión ===

            elif "nombre de la s/e" in label:
                data["nombre_subestacion"] = value

            elif "nivel de tensión" in label or "nivel de tension" in label:
                data["nivel_tension_kv"] = clean_row[3] if len(clean_row) > 3 else value

            elif "carácter de conexión" in label or "caracter de conexion" in label:
                # Valor puede estar más adelante
                char_value = ""
                for i in range(2, len(clean_row)):
                    if clean_row[i] and clean_row[i] not in ["Indefinido", "Temporal", "/", ""]:
                        if "indefinido" in clean_row[i].lower() or "temporal" in clean_row[i].lower():
                            char_value = clean_row[i]
                            break
                data["caracter_conexion"] = char_value

            elif "fecha estimada de declaración en construcción" in label or "fecha estimada de construccion" in label.lower():
                fecha_str = clean_row[6] if len(clean_row) > 6 else value
                data["fecha_estimada_construccion"] = self._parse_date(fecha_str)

            elif "fecha estimada de interconexión" in label or "fecha estimada de interconexion" in label:
                fecha_str = clean_row[6] if len(clean_row) > 6 else value
                data["fecha_estimada_interconexion"] = self._parse_date(fecha_str)

            # === SECCIÓN: Ubicación Geográfica del Punto de Conexión ===

            elif "coordenadas u.t.m." in label.lower() and "proyecto_coordenadas_utm_huso" in data:
                # Segunda aparición de coordenadas = ubicación del punto de conexión
                if "conexion_coordenadas_utm_huso" not in data:
                    if len(clean_row) > 3:
                        data["conexion_coordenadas_utm_huso"] = clean_row[3] + " " + clean_row[4] if len(clean_row) > 4 else clean_row[3]
                    if len(clean_row) > 6:
                        data["conexion_coordenadas_utm_este"] = clean_row[6]
                    if len(clean_row) > 8:
                        data["conexion_coordenadas_utm_norte"] = clean_row[8]

            elif label == "comuna" and "proyecto_comuna" in data:
                # Segunda aparición de comuna = comuna del punto de conexión
                data["conexion_comuna"] = value
                # Región típicamente está en columna[5-6]
                if len(clean_row) > 5 and "región" in clean_row[5].lower():
                    data["conexion_region"] = clean_row[6] if len(clean_row) > 6 else ""

        # Limpieza final
        if hasattr(self, '_next_coord'):
            delattr(self, '_next_coord')

        return data

    def _parse_decimal(self, value: str) -> Optional[float]:
        """
        Convierte string a decimal, manejando diferentes formatos.

        Args:
            value: Valor en string

        Returns:
            Float o None si no se puede convertir
        """
        if not value:
            return None

        # Limpiar el valor
        cleaned = value.replace(',', '.').strip()

        # Extraer primer número
        match = re.search(r'[-+]?\d*\.?\d+', cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None

        return None

    def _parse_date(self, value: str) -> Optional[str]:
        """
        Convierte fecha a formato ISO (YYYY-MM-DD).

        Maneja formatos: DD-MM-YYYY, DD/MM/YYYY, etc.

        Valida que la fecha sea real (ej: 31-02-2024 retorna None).

        Args:
            value: Fecha en string

        Returns:
            Fecha en formato ISO o None si fecha inválida
        """
        from datetime import datetime

        if not value:
            return None

        # Buscar patrón DD-MM-YYYY o DD/MM/YYYY
        match = re.search(r'(\d{1,2})[-/](\d{1,2})[-/](\d{4})', value)
        if match:
            day, month, year = match.groups()

            # Validar que el mes sea válido (1-12)
            month_int = int(month)
            if month_int > 12:
                # Probablemente el formato es MM-DD-YYYY
                day, month = month, day
                month_int = int(month)

            # Validar que la fecha sea real usando datetime
            try:
                day_int = int(day)
                year_int = int(year)

                # Intentar crear la fecha para validar que sea real
                # (esto rechaza 31-02-2024, 30-02-2024, etc.)
                datetime(year_int, month_int, day_int)

                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except (ValueError, Exception):
                # Fecha inválida (ej: 31-02-2024)
                logger.warning(f"⚠️  Fecha inválida detectada: {value}")
                return None

        return None

    def _parse_pdf_date(self, date_string: Optional[str]) -> Optional[str]:
        """
        Convierte fecha PDF (formato D:YYYYMMDDHHmmss) a formato MySQL DATETIME.

        Args:
            date_string: Fecha en formato PDF (ej: "D:20211118161022-03'00'")

        Returns:
            Fecha en formato MySQL DATETIME (ej: "2021-11-18 16:10:22") o None
        """
        from datetime import datetime

        if not date_string:
            return None

        try:
            # Formato típico: D:20211118161022-03'00'
            # Extraer solo la parte de fecha/hora: 20211118161022
            date_part = date_string.replace('D:', '').split('-')[0].split('+')[0].split('Z')[0]

            # Parsear: YYYYMMDDHHMMSS
            if len(date_part) >= 14:
                dt = datetime.strptime(date_part[:14], '%Y%m%d%H%M%S')
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            elif len(date_part) >= 8:
                # Solo fecha (YYYYMMDD)
                dt = datetime.strptime(date_part[:8], '%Y%m%d')
                return dt.strftime('%Y-%m-%d 00:00:00')
            else:
                return None

        except (ValueError, Exception) as e:
            logger.warning(f"⚠️  Fecha PDF inválida: {date_string} - {e}")
            return None


def parse_sac_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Función helper para parsear un formulario SAC desde PDF.

    Args:
        pdf_path: Ruta al archivo PDF

    Returns:
        Diccionario con datos extraídos
    """
    parser = SACPDFParser()
    return parser.parse(pdf_path)
