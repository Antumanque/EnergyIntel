"""
Parser de Formularios SAC en formato PDF.

Este módulo extrae datos estructurados de formularios SAC (Solicitud de
Autorización de Conexión) usando pdfplumber para detectar y parsear tablas.

Versión 2.6.0:
- OCR con Tesseract para PDFs escaneados
- pypdf fallback para texto plano
- Extracción progresiva de RUT con múltiples estrategias
- Extracción progresiva de razón_social (4 estrategias: estricto, permisivo, muy permisivo, keywords)
- Extracción progresiva de nombre_proyecto (4 estrategias: estricto, permisivo, muy permisivo, alternativo)
- Verificación de campos críticos post-tabla: activa pypdf fallback si pdfplumber no extrae campos (NUEVA)
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
    import pypdf
    PYPDF_AVAILABLE = True
except ImportError:
    PYPDF_AVAILABLE = False

logger = logging.getLogger(__name__)


class SACPDFParser:
    """
    Parser para Formularios SAC en PDF.

    Los formularios SAC son PDFs generados desde Excel que contienen
    una tabla estructurada con ~32 filas.
    """

    def __init__(self):
        """Inicializa el parser de SAC."""
        self.version = "2.4.0"  # OCR + pypdf fallback + RUT progresivo

    def parse(self, pdf_path: str, solicitud_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Parsea un formulario SAC desde PDF.

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
                    # Fallback Nivel 1: pypdf para extraer texto plano
                    logger.warning("⚠️  No se detectaron tablas, intentando pypdf...")
                    if PYPDF_AVAILABLE:
                        data = self._parse_with_pypdf_fallback(pdf_path)
                        if data and all(data.get(f) for f in ["razon_social", "rut", "nombre_proyecto"]):
                            data.update(pdf_metadata)
                            logger.info(f"✅ pypdf - Formulario SAC parseado: {data.get('nombre_proyecto', 'N/A')}")
                            return data

                    # Fallback Nivel 2: Detectar si es PDF escaneado
                    logger.warning("⚠️  pypdf no recuperó campos críticos...")
                    if self._is_scanned_pdf(pdf):
                        logger.warning("⚠️  PDF escaneado detectado, intentando OCR...")
                        if TESSERACT_AVAILABLE:
                            data = self._parse_with_ocr(pdf_path)
                            if data:
                                data.update(pdf_metadata)
                                logger.info(f"✅ OCR - Formulario SAC parseado: {data.get('nombre_proyecto', 'N/A')}")
                                return data
                        else:
                            logger.error("❌ Tesseract no disponible")

                    raise ValueError("No se detectaron tablas en el PDF y OCR no pudo extraer datos")

                table = tables[0]
                logger.debug(f"Tabla extraída: {len(table)} filas")

                # Parsear datos de la tabla
                data = self._parse_table(table)

                # Verificar si faltan campos críticos
                critical_fields = ['razon_social', 'rut', 'nombre_proyecto']
                missing_critical = [f for f in critical_fields if not data.get(f)]

                # Si faltan campos críticos, intentar fallback con pypdf
                if missing_critical:
                    logger.warning(f"⚠️  pdfplumber no encontró campos críticos: {', '.join(missing_critical)}")
                    logger.warning(f"   Activando pypdf fallback (extracción texto completo + regex progresivo)...")

                    if PYPDF_AVAILABLE:
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
                # Intentar extracción progresiva de RUT
                rut = self._extract_rut_progressive(value) if value else None
                if rut:
                    data["rut"] = rut
                else:
                    data["rut"] = value  # Fallback al valor original

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

    def _is_scanned_pdf(self, pdf: pdfplumber.PDF) -> bool:
        """
        Detecta si un PDF es escaneado (imagen) vs generado digitalmente.

        Heurística: Si el texto extraíble es muy corto (<50 caracteres),
        probablemente es un PDF escaneado.
        """
        try:
            full_text = ""
            for page in pdf.pages:
                full_text += page.extract_text() or ""

            return len(full_text.strip()) < 50
        except:
            return False

    def _parse_with_ocr(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """
        Parsea PDF usando OCR (Tesseract).

        Convierte PDF a imágenes y aplica OCR para extraer texto.
        """
        if not TESSERACT_AVAILABLE:
            return None

        try:
            # Convertir PDF a imágenes
            images = pdf2image.convert_from_path(pdf_path, dpi=300)

            full_text = ""
            for i, image in enumerate(images):
                logger.debug(f"  Aplicando OCR a página {i+1}...")
                # OCR con idioma español
                text = pytesseract.image_to_string(image, lang='spa')
                full_text += text + "\n\n"

            if not full_text.strip():
                return None

            # Extraer campos con regex sobre el texto OCR
            data = {}

            # RUT con extracción progresiva
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut
                logger.debug(f"  ✅ OCR - RUT: {rut}")

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

            return data if data else None

        except Exception as e:
            logger.error(f"❌ Error en OCR: {e}")
            return None

    def _parse_with_pypdf_fallback(self, pdf_path: str) -> Optional[Dict[str, Any]]:
        """
        Parsea PDF usando pypdf (extracción de texto plano).

        Útil para PDFs donde pdfplumber no detecta tablas pero el texto
        está disponible en formato plano.
        """
        if not PYPDF_AVAILABLE:
            return None

        try:
            reader = pypdf.PdfReader(pdf_path)
            full_text = ""
            for page in reader.pages:
                full_text += page.extract_text() or ""

            if not full_text.strip():
                return None

            # Extraer campos con regex sobre el texto plano
            data = {}

            # RUT con extracción progresiva
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut
                logger.debug(f"  ✅ Campo recuperado con pypdf: rut = {rut}")

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

            return data if data else None

        except Exception as e:
            logger.error(f"❌ Error en pypdf: {e}")
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
            # Validar longitud mínima
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
        # Buscar patrones como "ALGO S.A.", "ALGO LTDA", "ALGO SpA"
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
                # Agregar el tipo societario de vuelta
                full_match = match.group(0).strip()
                if len(razon) >= 3 and len(razon) <= 150:
                    return full_match

        return None

    def _extract_nombre_proyecto_progressive(self, text: str) -> Optional[str]:
        """
        Extrae nombre del proyecto con estrategia progresiva.

        Estrategias:
        0. Header SAC: Busca "Proyecto [NOMBRE] SAC" en headers del documento
        1. Estricto: "Nombre del Proyecto" + mayúscula inicial
        2. Permisivo: Acepta más caracteres especiales, más stopwords
        3. Muy permisivo: Captura hasta encontrar campo siguiente
        4. Alternativo: Busca "Proyecto:" o "Nombre:"
        """
        if not text:
            return None

        # Estrategia 0: Header "Proyecto [NOMBRE] SAC" (específico para formularios SAC)
        header_match = re.search(
            r'Proyecto\s+([A-ZÁÉÍÓÚÑ][A-Za-záéíóúñ0-9\s\.,\-&\(\)]+?)\s+SAC',
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
            r'Proyecto[:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ0-9\s\.,\-&\(\)"/]+?)(?:\n\n|Tipo|Potencia)',
            r'(?:^|\n)Nombre[:\s]+([A-Za-záéíóúñÁÉÍÓÚÑ0-9\s\.,\-&\(\)"/]+?)(?:\n\n|Tipo|Potencia)',
        ]

        for pattern in alt_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                nombre = match.group(1).strip()
                if len(nombre) >= 3 and len(nombre) <= 200:
                    return nombre

        return None

    def _extract_rut_progressive(self, text: str) -> Optional[str]:
        """
        Extrae RUT con estrategia progresiva (estricto → permisivo → muy permisivo).

        Estrategias:
        1. Formato estricto: XX.XXX.XXX-X o XXXXXXXX-X
        2. Formato permisivo: Acepta espacios o puntos opcionales
        3. Formato muy permisivo: Solo dígitos + guión
        """
        if not text:
            return None

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
        rut_match = re.search(r'(\d{1,2})[\.\s]?(\d{3})[\.\s]?(\d{3})-?([\dkK])', text)
        if rut_match:
            partes = rut_match.groups()
            rut_reconstruido = f"{partes[0]}.{partes[1]}.{partes[2]}-{partes[3]}"
            logger.debug(f"  RUT encontrado (permisivo): {rut_match.group(0)} → {rut_reconstruido}")
            return rut_reconstruido

        # Estrategia 4: Muy permisivo - buscar secuencia de 7-9 dígitos seguidos de K o dígito
        rut_match = re.search(r'(\d{7,9})[\s\-]?([\dkK])', text)
        if rut_match:
            numeros = rut_match.group(1)
            dv = rut_match.group(2)

            # Validar longitud razonable para RUT chileno
            if 7 <= len(numeros) <= 8:
                rut_sin_puntos = f"{numeros}-{dv}"
                rut_normalizado = self._normalize_rut(rut_sin_puntos)
                logger.debug(f"  RUT encontrado (muy permisivo): {rut_match.group(0)} → {rut_normalizado}")
                return rut_normalizado

        return None

    def _normalize_rut(self, rut: str) -> str:
        """
        Normaliza RUT al formato estándar XX.XXX.XXX-X.

        Args:
            rut: RUT sin puntos (ej: "12345678-9")

        Returns:
            RUT normalizado (ej: "12.345.678-9")
        """
        # Remover puntos existentes y espacios
        rut = rut.replace('.', '').replace(' ', '')

        # Separar número y dígito verificador
        if '-' in rut:
            num, dv = rut.split('-')
        else:
            num, dv = rut[:-1], rut[-1]

        # Formatear con puntos
        num = num.zfill(8)  # Pad con ceros a la izquierda si es necesario
        num_formateado = f"{num[:-6]}.{num[-6:-3]}.{num[-3:]}"

        # Remover ceros iniciales del primer grupo
        num_formateado = num_formateado.lstrip('0').lstrip('.')

        return f"{num_formateado}-{dv.upper()}"

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
