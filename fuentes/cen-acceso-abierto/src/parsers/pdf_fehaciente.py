"""
Parser de Formularios Fehaciente en formato PDF.

Este módulo extrae datos estructurados de formularios Fehaciente
(Proyecto Fehaciente) usando pdfplumber
para detectar y parsear tablas.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any
import pdfplumber

logger = logging.getLogger(__name__)


class FehacientePDFParser:
    """
    Parser para Formularios Fehaciente en PDF.

    Los formularios Fehaciente son PDFs generados desde Excel que contienen
    una tabla estructurada similar a SAC pero con campos específicos.
    """

    def __init__(self):
        """Inicializa el parser de Fehaciente."""
        self.version = "1.0.0"

    def parse(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parsea un formulario Fehaciente desde PDF.

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

        logger.info(f"📄 Parseando formulario Fehaciente: {pdf_file.name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Formularios Fehaciente típicamente tienen 1-2 páginas
                if len(pdf.pages) == 0:
                    raise ValueError("PDF sin páginas")

                # Extraer metadata del PDF
                metadata = pdf.metadata or {}
                pdf_metadata = {
                    'pdf_producer': metadata.get('Producer'),
                    'pdf_author': metadata.get('Author'),
                    'pdf_title': metadata.get('Title'),
                    'pdf_creation_date': self._parse_pdf_date(metadata.get('CreationDate')),
                }

                # Procesar todas las páginas
                all_tables = []
                for page_num, page in enumerate(pdf.pages, 1):
                    tables = page.extract_tables()
                    if tables:
                        logger.debug(f"Página {page_num}: {len(tables)} tabla(s) encontrada(s)")
                        all_tables.extend(tables)

                if not all_tables:
                    raise ValueError("No se detectaron tablas en el PDF")

                # Parsear datos de la primera tabla (o combinar todas)
                data = self._parse_table(all_tables[0])

                # Agregar metadata del PDF
                data.update(pdf_metadata)

                logger.info(f"✅ Formulario Fehaciente parseado: {data.get('nombre_proyecto', 'N/A')}")
                return data

        except Exception as e:
            logger.error(f"❌ Error al parsear Fehaciente: {str(e)}", exc_info=True)
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

            # === SECCIÓN: Antecedentes de la Empresa Solicitante ===

            if "razón social" in label or "razon social" in label:
                data["razon_social"] = value

            elif label == "rut":
                data["rut"] = self._normalize_rut(value)

            elif "domicilio legal" in label:
                data["domicilio_legal"] = value

            # === SECCIÓN: Representante Legal ===

            elif "nombre del representante legal" in label:
                # El valor puede estar en columna[3] o [4]
                value = clean_row[3] if len(clean_row) > 3 and clean_row[3] else value
                data["representante_legal_nombre"] = value

            elif label == "e-mail" and "representante_legal_nombre" in data:
                # Primer email es del representante legal
                data["representante_legal_email"] = value

            elif label == "teléfono" and "representante_legal_nombre" in data and "representante_legal_email" in data:
                # Teléfono del representante
                data["representante_legal_telefono"] = value

            # === SECCIÓN: Coordinadores de Proyectos ===

            elif "nombre primer coordinador" in label or ("coordinador de proyecto" in label and "coordinador_proyecto_1_nombre" not in data):
                coord_nombre = clean_row[3] if len(clean_row) > 3 and clean_row[3] else value
                data["coordinador_proyecto_1_nombre"] = coord_nombre
                self._next_coord = 1

            elif "nombre segundo coordinador" in label or ("coordinador de proyecto" in label and "coordinador_proyecto_1_nombre" in data):
                coord_nombre = clean_row[3] if len(clean_row) > 3 and clean_row[3] else value
                data["coordinador_proyecto_2_nombre"] = coord_nombre
                self._next_coord = 2

            elif "e-mail primer coordinador" in label or (label == "e-mail" and hasattr(self, '_next_coord') and self._next_coord == 1):
                data["coordinador_proyecto_1_email"] = value

            elif "e-mail segundo coordinador" in label or (label == "e-mail" and hasattr(self, '_next_coord') and self._next_coord == 2):
                data["coordinador_proyecto_2_email"] = value

            elif "teléfono primer coordinador" in label or ("telefono primer" in label):
                data["coordinador_proyecto_1_telefono"] = value

            elif "teléfono segundo coordinador" in label or ("telefono segundo" in label):
                data["coordinador_proyecto_2_telefono"] = value

            # === SECCIÓN: Antecedentes del Proyecto ===

            elif "nombre del proyecto" in label:
                data["nombre_proyecto"] = clean_row[3] if len(clean_row) > 3 else value

            elif "tipo de proyecto" in label or "tipo proyecto" in label:
                data["tipo_proyecto"] = value

            elif "tipo de tecnología" in label or "tipo tecnologia" in label:
                data["tipo_tecnologia"] = value

            elif "potencia neta solicitada de inyección" in label or "potencia neta de inyeccion" in label:
                data["potencia_neta_inyeccion_mw"] = self._parse_decimal(value)

            elif "potencia neta solicitada de retiro" in label or "potencia neta de retiro" in label:
                data["potencia_neta_retiro_mw"] = self._parse_decimal(value)

            elif "factor de potencia nominal" in label:
                data["factor_potencia_nominal"] = self._parse_decimal(value)

            elif "modo de control inversores" in label or "modo de control" in label:
                data["modo_control_inversores"] = value

            # === SECCIÓN: Parámetros Sistemas de Almacenamiento ===

            elif "componente generación" in label or "componente generacion" in label:
                data["componente_generacion"] = value

            elif "componente de almacenamiento" in label:
                data["componente_almacenamiento"] = value

            elif "potencia [mw]" in label and "componente_generacion" in data and "componente_generacion_potencia_mw" not in data:
                # Primera aparición de "Potencia [MW]" es para generación
                data["componente_generacion_potencia_mw"] = self._parse_decimal(value)

            elif "potencia [mw]" in label and "componente_almacenamiento" in data and "componente_almacenamiento_potencia_mw" not in data:
                # Segunda aparición es para almacenamiento
                data["componente_almacenamiento_potencia_mw"] = self._parse_decimal(value)

            elif "energía [mwh]" in label or "energia [mwh]" in label:
                data["componente_almacenamiento_energia_mwh"] = self._parse_decimal(value)

            elif "horas de almacenamiento" in label:
                data["componente_almacenamiento_horas"] = self._parse_decimal(value)

            # === SECCIÓN: Ubicación Geográfica del Proyecto ===

            elif "coordenadas u.t.m." in label.lower() and "proyecto_coordenadas_utm_huso" not in data:
                # Primera aparición = ubicación del proyecto
                if len(clean_row) > 3:
                    data["proyecto_coordenadas_utm_huso"] = clean_row[3]
                if len(clean_row) > 5:
                    data["proyecto_coordenadas_utm_este"] = self._parse_coordinate(clean_row[5])
                if len(clean_row) > 7:
                    data["proyecto_coordenadas_utm_norte"] = self._parse_coordinate(clean_row[7])

            elif label == "comuna" and "proyecto_comuna" not in data:
                # Primera aparición de comuna = comuna del proyecto
                data["proyecto_comuna"] = value
                # Región típicamente está más adelante
                if len(clean_row) > 5 and "región" in clean_row[5].lower():
                    data["proyecto_region"] = clean_row[6] if len(clean_row) > 6 else ""

            # === SECCIÓN: Antecedentes del Punto de Conexión ===

            elif "nombre de la s/e" in label or "nombre de la se" in label or "línea de transmisión" in label:
                data["nombre_se_o_linea"] = value

            elif "tipo de conexión" in label or "tipo de conexion" in label:
                data["tipo_conexion"] = value

            elif "seccionamiento o derivación" in label and "distanci" in label:
                # Distancia para seccionamiento o derivación
                data["seccionamiento_distancia_km"] = self._parse_decimal(value)

            elif "nombre s/e más cercana" in label or "se mas cercana" in label:
                data["seccionamiento_se_cercana"] = value

            elif "nivel de tensión" in label or "nivel de tension" in label:
                data["nivel_tension_kv"] = value

            elif "paño" in label or "estructura" in label:
                data["pano_o_estructura"] = value

            elif "fecha estimada de declaración en construcción" in label or "fecha estimada de construccion" in label.lower():
                fecha_str = clean_row[3] if len(clean_row) > 3 else value
                data["fecha_estimada_construccion"] = self._parse_date(fecha_str)

            elif "fecha estimada de entrada en operación" in label or "fecha estimada de operacion" in label:
                fecha_str = clean_row[3] if len(clean_row) > 3 else value
                data["fecha_estimada_operacion"] = self._parse_date(fecha_str)

            # === SECCIÓN: Ubicación Geográfica del Punto de Conexión ===

            elif "coordenadas u.t.m." in label.lower() and "proyecto_coordenadas_utm_huso" in data:
                # Segunda aparición = ubicación del punto de conexión
                if "conexion_coordenadas_utm_huso" not in data:
                    if len(clean_row) > 3:
                        data["conexion_coordenadas_utm_huso"] = clean_row[3]
                    if len(clean_row) > 5:
                        data["conexion_coordenadas_utm_este"] = self._parse_coordinate(clean_row[5])
                    if len(clean_row) > 7:
                        data["conexion_coordenadas_utm_norte"] = self._parse_coordinate(clean_row[7])

            elif label == "comuna" and "proyecto_comuna" in data:
                # Segunda aparición = comuna del punto de conexión
                data["conexion_comuna"] = value
                if len(clean_row) > 5 and "región" in clean_row[5].lower():
                    data["conexion_region"] = clean_row[6] if len(clean_row) > 6 else ""

            elif "información adicional" in label or "informacion adicional" in label:
                data["informacion_adicional"] = value

        # Limpieza final
        if hasattr(self, '_next_coord'):
            delattr(self, '_next_coord')

        return data

    def _normalize_rut(self, rut: Optional[str]) -> Optional[str]:
        """
        Normaliza un RUT al formato estándar XX.XXX.XXX-X.

        Args:
            rut: RUT en cualquier formato

        Returns:
            RUT normalizado o None
        """
        if not rut:
            return None

        # Eliminar puntos, guiones, espacios
        rut_clean = rut.replace(".", "").replace("-", "").replace(" ", "").upper()

        if not rut_clean or len(rut_clean) < 2:
            return rut

        cuerpo = rut_clean[:-1]
        dv = rut_clean[-1]

        if not cuerpo.isdigit():
            return rut

        # Agregar puntos cada 3 dígitos desde la derecha
        cuerpo_formateado = ""
        for i, digit in enumerate(reversed(cuerpo)):
            if i > 0 and i % 3 == 0:
                cuerpo_formateado = "." + cuerpo_formateado
            cuerpo_formateado = digit + cuerpo_formateado

        return f"{cuerpo_formateado}-{dv}"

    def _parse_coordinate(self, coord: Optional[str]) -> Optional[float]:
        """
        Convierte coordenada UTM a float.

        Args:
            coord: Coordenada (Este o Norte)

        Returns:
            Coordenada como float o None
        """
        return self._parse_decimal(coord)

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
                datetime(year_int, month_int, day_int)

                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except (ValueError, Exception):
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


def parse_fehaciente_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Función helper para parsear un formulario Fehaciente desde PDF.

    Args:
        pdf_path: Ruta al archivo PDF

    Returns:
        Diccionario con datos extraídos
    """
    parser = FehacientePDFParser()
    return parser.parse(pdf_path)
