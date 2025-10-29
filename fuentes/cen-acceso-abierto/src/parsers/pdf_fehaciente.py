"""
Parser de Formularios Fehaciente en formato PDF.

Este módulo extrae datos estructurados de formularios Fehaciente
(Proyecto Fehaciente) usando pdfplumber
para detectar y parsear tablas.

Versión 2.5.0:
- OCR con Tesseract para PDFs escaneados
- pypdf fallback para texto plano
- Extracción progresiva de RUT con múltiples estrategias
- Extracción progresiva de razón_social (4 estrategias: estricto, permisivo, muy permisivo, keywords) (NUEVA)
- Extracción progresiva de nombre_proyecto (5 estrategias: header, estricto, permisivo, muy permisivo, alternativo) (NUEVA)
- Logging mejorado para pypdf fallback (NUEVA)
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any
import pdfplumber

# Importaciones para fallbacks
try:
    import pytesseract
    from PIL import Image
    import pdf2image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    from pypdf import PdfReader
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class FehacientePDFParser:
    """
    Parser para Formularios Fehaciente en PDF.

    Los formularios Fehaciente son PDFs generados desde Excel que contienen
    una tabla estructurada similar a SAC pero con campos específicos.
    """

    def __init__(self):
        """Inicializa el parser de Fehaciente."""
        self.version = "2.4.0"  # OCR + pypdf fallback + RUT progresivo

    def parse(self, pdf_path: str, solicitud_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Parsea un formulario Fehaciente desde PDF.

        Args:
            pdf_path: Ruta al archivo PDF
            solicitud_id: ID de solicitud (opcional, para multi-página)

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
                    # No se detectaron tablas - puede ser PDF escaneado
                    logger.warning("⚠️  No se detectaron tablas en el PDF")

                    # Intentar detectar si es PDF escaneado y aplicar OCR
                    if self._is_scanned_pdf(pdf_path):
                        logger.warning(f"⚠️  PDF escaneado detectado, activando OCR...")
                        data = self._parse_with_ocr(pdf_path)

                        # Agregar metadata y retornar
                        data.update(pdf_metadata)

                        # Verificar si OCR extrajo campos críticos
                        critical_fields = ['razon_social', 'rut', 'nombre_proyecto']
                        campos_extraidos = sum(1 for f in critical_fields if data.get(f))

                        if campos_extraidos == 0:
                            raise ValueError("No se detectaron tablas en el PDF y OCR no pudo extraer datos")

                        logger.info(f"✅ Formulario Fehaciente parseado con OCR: {data.get('nombre_proyecto', 'N/A')}")
                        return data
                    else:
                        raise ValueError("No se detectaron tablas en el PDF")

                # Parsear datos de la primera tabla (o combinar todas)
                data = self._parse_table(all_tables[0])

                # Verificar si faltan campos críticos
                critical_fields = ['razon_social', 'rut', 'nombre_proyecto']
                missing_critical = [f for f in critical_fields if not data.get(f)]

                # Si faltan campos críticos, intentar fallback con pypdf
                if missing_critical:
                    logger.warning(f"⚠️  pdfplumber no encontró campos críticos: {', '.join(missing_critical)}")
                    logger.warning(f"   Activando pypdf fallback (extracción texto completo + regex progresivo)...")
                    fallback_data = self._parse_with_pypdf_fallback(pdf_path)

                    # Sobrescribir solo los campos que estaban vacíos
                    for field in missing_critical:
                        if fallback_data.get(field):
                            data[field] = fallback_data[field]
                            logger.info(f"  ✅ Campo recuperado con pypdf: {field} = {fallback_data[field]}")

                    # Verificar si pypdf recuperó todos los campos
                    still_missing = [f for f in critical_fields if not data.get(f)]
                    if still_missing:
                        logger.warning(f"⚠️  pypdf no pudo recuperar: {', '.join(still_missing)}")

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

    def _parse_with_pypdf_fallback(self, pdf_path: str) -> Dict[str, Any]:
        """
        Fallback parser usando pypdf para extracción de texto plano.

        Útil cuando pdfplumber detecta tablas pero no puede parsearlas correctamente.

        Busca patrones de texto específicos para Fehaciente:
        - "Nombre del Proyecto <nombre>"
        - "Razón Social <razón social>"
        - RUT en formato XX.XXX.XXX-X

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Diccionario con campos extraídos del texto plano
        """
        logger.info("🔄 Intentando fallback con pypdf...")

        data = {}

        try:
            reader = PdfReader(pdf_path)
            full_text = ""

            # Extraer todo el texto
            for page in reader.pages:
                full_text += page.extract_text()

            # Buscar campos con extracción progresiva

            # Razón Social con extracción progresiva
            razon = self._extract_razon_social_progressive(full_text)
            if razon:
                data['razon_social'] = razon
                logger.debug(f"  ✅ Campo recuperado con pypdf: razon_social = {razon}")

            # Nombre del Proyecto con extracción progresiva
            nombre = self._extract_nombre_proyecto_progressive(full_text)
            if nombre:
                data['nombre_proyecto'] = nombre
                logger.debug(f"  ✅ Campo recuperado con pypdf: nombre_proyecto = {nombre}")

            # RUT: Extracción progresiva (estricto → permisivo)
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut
                logger.debug(f"  ✅ Campo recuperado con pypdf: rut = {rut}")

            campos_recuperados = [k for k in ['razon_social', 'nombre_proyecto', 'rut'] if data.get(k)]
            logger.info(f"✅ Fallback pypdf recuperó {len(campos_recuperados)} campos: {', '.join(campos_recuperados)}")

            return data

        except Exception as e:
            logger.error(f"❌ Error en fallback pypdf: {str(e)}")
            return data

    def _extract_rut_progressive(self, text: str) -> Optional[str]:
        """
        Extrae RUT con estrategia progresiva (estricto → permisivo → muy permisivo).

        Útil para texto OCR donde los puntos pueden desaparecer o convertirse en espacios.

        Estrategias:
        1. Formato estricto: XX.XXX.XXX-X o XXXXXXXX-X
        2. Formato permisivo: Acepta espacios o puntos opcionales
        3. Formato muy permisivo: Solo dígitos + guión

        Args:
            text: Texto donde buscar el RUT

        Returns:
            RUT normalizado en formato XX.XXX.XXX-X o None
        """
        # Estrategia 1: Formato estricto (con puntos)
        rut_match = re.search(r'(\d{1,2}\.\d{3}\.\d{3}-[\dkK])', text)
        if rut_match:
            logger.debug(f"  RUT encontrado (estricto): {rut_match.group(0)}")
            return rut_match.group(0)

        # Estrategia 2: Formato sin puntos pero con guión
        rut_match = re.search(r'(\d{7,8}-[\dkK])', text)
        if rut_match:
            rut_sin_puntos = rut_match.group(0)
            rut_normalizado = self._normalize_rut(rut_sin_puntos)
            logger.debug(f"  RUT encontrado (sin puntos): {rut_sin_puntos} → {rut_normalizado}")
            return rut_normalizado

        # Estrategia 3: Formato permisivo (espacios o puntos opcionales)
        # Patrón: XX XXX XXX-X o XX.XXX.XXX-X o combinaciones
        rut_match = re.search(r'(\d{1,2})[\.\s]?(\d{3})[\.\s]?(\d{3})-?([\dkK])', text)
        if rut_match:
            # Reconstruir con formato estándar
            partes = rut_match.groups()
            rut_reconstruido = f"{partes[0]}.{partes[1]}.{partes[2]}-{partes[3]}"
            logger.debug(f"  RUT encontrado (permisivo): {rut_match.group(0)} → {rut_reconstruido}")
            return rut_reconstruido

        # Estrategia 4: Muy permisivo - buscar secuencia de 7-9 dígitos seguidos de K o dígito
        rut_match = re.search(r'(\d{7,9})[\s\-]?([\dkK])', text)
        if rut_match:
            numeros = rut_match.group(1)
            dv = rut_match.group(2)

            # Validar que tiene sentido como RUT (longitud correcta)
            if 7 <= len(numeros) <= 8:
                rut_sin_puntos = f"{numeros}-{dv}"
                rut_normalizado = self._normalize_rut(rut_sin_puntos)
                logger.debug(f"  RUT encontrado (muy permisivo): {rut_match.group(0)} → {rut_normalizado}")
                return rut_normalizado

        return None

    def _extract_razon_social_progressive(self, text: str) -> Optional[str]:
        """
        Extrae razón social con estrategia progresiva (estricto → permisivo → muy permisivo → keywords).

        Estrategias:
        1. Estricto: Razón Social + mayúscula inicial + caracteres limitados
        2. Permisivo: Acepta números, &, paréntesis, más stopwords
        3. Muy permisivo: Captura hasta encontrar RUT o salto de línea doble
        4. Keywords: Busca patrones como S.A., LTDA, SpA, CIA
        """
        if not text:
            return None

        # Estrategia 1: Formato estricto (actual)
        razon_match = re.search(
            r'Razón\s+Social[:\s]*([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ\s\.,]+?)(?:\n|RUT|Giro)',
            text, re.IGNORECASE
        )
        if razon_match:
            return razon_match.group(1).strip()

        # Estrategia 2: Formato permisivo (acepta números, &, paréntesis, guiones)
        razon_match = re.search(
            r'Razón\s+Social[:\s]*([A-ZÁÉÍÓÚÑ0-9][A-Za-záéíóúñ0-9\s\.,\-&\(\)]+?)(?:\n\n|RUT|Giro|Domicilio|Comuna|Región)',
            text, re.IGNORECASE
        )
        if razon_match:
            razon = razon_match.group(1).strip()
            if len(razon) >= 3:
                return razon

        # Estrategia 3: Muy permisivo (captura hasta RUT o doble salto)
        razon_match = re.search(
            r'Razón\s+Social[:\s]*([^\n]+?)(?=\n\s*(?:RUT|Giro|Domicilio))',
            text, re.IGNORECASE
        )
        if razon_match:
            razon = razon_match.group(1).strip()
            if len(razon) >= 3 and len(razon) <= 150:
                return razon

        # Estrategia 4: Búsqueda por keywords corporativos
        keyword_patterns = [
            r'([A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.,\-&]+?)\s+S\.?A\.?(?:\s|$|\n)',
            r'([A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.,\-&]+?)\s+LTDA\.?(?:\s|$|\n)',
            r'([A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.,\-&]+?)\s+SpA\.?(?:\s|$|\n)',
            r'([A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.,\-&]+?)\s+C[IÍ]A\.?(?:\s|$|\n)',
            r'([A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.,\-&]+?)\s+SOCIEDAD\s+AN[OÓ]NIMA(?:\s|$|\n)',
        ]

        for pattern in keyword_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                razon = match.group(1).strip()
                full_match = match.group(0).strip()
                if len(razon) >= 3 and len(razon) <= 150:
                    return full_match

        return None

    def _extract_nombre_proyecto_progressive(self, text: str) -> Optional[str]:
        """
        Extrae nombre del proyecto con estrategia progresiva.

        Estrategias:
        0. Header: Busca "Proyecto [NOMBRE]" en headers del documento
        1. Estricto: "Nombre del Proyecto" + mayúscula inicial
        2. Permisivo: Acepta más caracteres especiales, más stopwords
        3. Muy permisivo: Captura hasta encontrar campo siguiente
        4. Alternativo: Busca "Proyecto:" o "Nombre:"
        """
        if not text:
            return None

        # Estrategia 0: Header "Proyecto [NOMBRE]" (genérico)
        header_match = re.search(
            r'Proyecto\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s\.,\-&\(\)]+?)(?:\n|$|  )',
            text, re.IGNORECASE
        )
        if header_match:
            nombre = header_match.group(1).strip()
            # Validar longitud razonable
            if 3 <= len(nombre) <= 80:
                return nombre

        # Estrategia 1: Formato estricto (actual)
        nombre_match = re.search(
            r'Nombre\s+del\s+Proyecto[:\s]*([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s\.,\-]+?)(?:\n|Tipo)',
            text, re.IGNORECASE
        )
        if nombre_match:
            return nombre_match.group(1).strip()

        # Estrategia 2: Formato permisivo (acepta paréntesis, &, más stopwords)
        nombre_match = re.search(
            r'Nombre\s+del\s+Proyecto[:\s]*([A-ZÁÉÍÓÚÑ0-9][A-Za-záéíóúñ0-9\s\.,\-&\(\)\"/]+?)(?:\n\n|Tipo|Potencia|Tecnología|Ubicación)',
            text, re.IGNORECASE
        )
        if nombre_match:
            nombre = nombre_match.group(1).strip()
            if len(nombre) >= 3:
                return nombre

        # Estrategia 3: Muy permisivo (captura hasta doble salto o campo siguiente)
        nombre_match = re.search(
            r'Nombre\s+del\s+Proyecto[:\s]*([^\n]+?)(?=\n\s*(?:Tipo|Potencia|Tecnología))',
            text, re.IGNORECASE
        )
        if nombre_match:
            nombre = nombre_match.group(1).strip()
            if len(nombre) >= 3 and len(nombre) <= 200:
                return nombre

        # Estrategia 4: Patrones alternativos ("Proyecto:", "Nombre:")
        alt_patterns = [
            r'(?:^|\n)Nombre[:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ0-9\s\.,\-&\(\)"/]+?)(?:\n\n|Tipo|Potencia)',
        ]

        for pattern in alt_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                nombre = match.group(1).strip()
                if len(nombre) >= 3 and len(nombre) <= 200:
                    return nombre

        return None

    def _is_scanned_pdf(self, pdf_path: str) -> bool:
        """
        Detecta si un PDF es escaneado (imagen-based) con bajo contenido de texto.

        Estrategia: Intenta extraer texto de la primera página.
        Si extrae menos de 50 caracteres, es probablemente un PDF escaneado.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            True si es PDF escaneado, False si tiene texto extraíble
        """
        try:
            reader = PdfReader(pdf_path)
            if len(reader.pages) == 0:
                return False

            # Extraer texto de primera página
            text = reader.pages[0].extract_text()
            text_length = len(text.strip())

            logger.debug(f"  Longitud texto extraído página 1: {text_length} caracteres")

            # Umbral: <50 caracteres = PDF escaneado
            return text_length < 50

        except Exception as e:
            logger.warning(f"⚠️  Error detectando si es PDF escaneado: {str(e)}")
            return False

    def _parse_with_ocr(self, pdf_path: str) -> Dict[str, Any]:
        """
        Parser usando Tesseract OCR para PDFs escaneados (imagen-based).

        Proceso:
        1. Convierte PDF a imágenes (pdf2image) con 300 DPI
        2. Aplica OCR con Tesseract (idioma español)
        3. Extrae campos con regex sobre texto OCR

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Diccionario con campos extraídos del texto OCR
        """
        logger.info("🔄 Intentando OCR con Tesseract (PDF escaneado detectado)...")

        data = {}

        try:
            import pytesseract
            from pdf2image import convert_from_path

            # Convertir PDF a imágenes (300 DPI para buena calidad)
            images = convert_from_path(pdf_path, dpi=300)
            logger.info(f"  Convertidas {len(images)} páginas a imágenes")

            # Aplicar OCR a cada página
            full_text = ""
            for i, image in enumerate(images, 1):
                logger.debug(f"  Aplicando OCR a página {i}/{len(images)}...")
                text = pytesseract.image_to_string(image, lang='spa')
                full_text += text + "\n"

            logger.info(f"  OCR extrajo {len(full_text)} caracteres")

            # Extraer campos con extracción progresiva adaptada para OCR

            # Razón Social con extracción progresiva
            razon = self._extract_razon_social_progressive(full_text)
            if razon:
                data['razon_social'] = razon
                logger.debug(f"  ✅ OCR - Razón Social: {razon}")

            # Nombre del Proyecto con extracción progresiva
            nombre = self._extract_nombre_proyecto_progressive(full_text)
            if nombre:
                data['nombre_proyecto'] = nombre
                logger.debug(f"  ✅ OCR - Nombre Proyecto: {nombre}")

            # RUT: Extracción progresiva (estricto → permisivo)
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut
                logger.info(f"  ✅ OCR - RUT: {data['rut']}")

            if not data:
                logger.warning("⚠️  OCR no pudo extraer ningún campo")
            else:
                logger.info(f"✅ OCR extrajo {len(data)} campo(s)")

            return data

        except ImportError as e:
            logger.error(f"❌ Tesseract no está instalado o falta dependencia: {e}")
            logger.info("   Ver scripts/TESSERACT_INSTALL.md para instrucciones de instalación")
            return {}

        except Exception as e:
            logger.error(f"❌ Error en OCR: {str(e)}")
            return {}


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
