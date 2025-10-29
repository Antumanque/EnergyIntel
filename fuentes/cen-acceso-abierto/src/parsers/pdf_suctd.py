"""
Parser de Formularios SUCTD en formato PDF.

Este módulo extrae datos estructurados de formularios SUCTD
(Solicitud de Uso de Capacidad Técnica Dedicada) usando pdfplumber
para detectar y parsear tablas.
"""

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Any, List
import pdfplumber
from pypdf import PdfReader

logger = logging.getLogger(__name__)


class SUCTDPDFParser:
    """
    Parser para Formularios SUCTD en PDF.

    Los formularios SUCTD son PDFs generados desde Excel que contienen
    una tabla estructurada similar a SAC pero con campos específicos.
    """

    def __init__(self):
        """Inicializa el parser de SUCTD."""
        self.version = "2.4.0"  # Versión con extracción mejorada de RUT (regex permisivo)

    def _find_value_in_row(
        self,
        clean_row: list,
        label_idx: int,
        min_length: int = 3
    ) -> str:
        """
        Busca el primer valor no vacío después de la posición del label.

        Mejora sobre la versión 1.0.0 que asumía posiciones fijas.
        Ahora busca en TODAS las columnas después del label.

        Args:
            clean_row: Fila con celdas limpias (strings)
            label_idx: Índice de la columna donde está el label
            min_length: Longitud mínima del valor (default: 3 caracteres)

        Returns:
            Primer valor encontrado, o string vacío si no hay ninguno
        """
        for idx in range(label_idx + 1, len(clean_row)):
            cell = clean_row[idx]
            if cell and len(cell) >= min_length:
                return cell
        return ""

    def _find_label_idx(self, clean_row: list, keywords: list) -> int:
        """
        Busca la posición de un label en la fila.

        Args:
            clean_row: Fila con celdas limpias
            keywords: Lista de keywords a buscar (ej: ["razón social", "razon social"])

        Returns:
            Índice de la columna donde se encontró el label, o -1 si no se encuentra
        """
        for idx, cell in enumerate(clean_row):
            cell_lower = cell.lower()
            for keyword in keywords:
                if keyword in cell_lower:
                    return idx
        return -1

    def parse(self, pdf_path: str, solicitud_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Parsea un formulario SUCTD desde PDF.

        Args:
            pdf_path: Ruta al archivo PDF
            solicitud_id: ID de la solicitud (opcional). Si se proporciona, permite
                         buscar datos faltantes en documentos hermanos.

        Returns:
            Diccionario con datos extraídos del formulario (incluye metadata del PDF)

        Raises:
            FileNotFoundError: Si el archivo no existe
            Exception: Si hay error al parsear
        """
        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {pdf_path}")

        logger.info(f"📄 Parseando formulario SUCTD: {pdf_file.name}")

        try:
            with pdfplumber.open(pdf_path) as pdf:
                # Formularios SUCTD típicamente tienen 1-2 páginas
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

                        logger.info(f"✅ Formulario SUCTD parseado con OCR: {data.get('nombre_proyecto', 'N/A')}")
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
                    fallback_data = self._parse_with_pypdf_fallback(pdf_path)

                    # Sobrescribir solo los campos que estaban vacíos
                    for field in missing_critical:
                        if fallback_data.get(field):
                            data[field] = fallback_data[field]
                            logger.info(f"✅ Campo recuperado con pypdf: {field} = {fallback_data[field]}")

                    # Actualizar lista de campos aún faltantes
                    missing_critical = [f for f in critical_fields if not data.get(f)]

                    # Si aún faltan campos Y tenemos solicitud_id, buscar en hermanos
                    if missing_critical and solicitud_id:
                        # Extraer ruta base (sin downloads/)
                        base_path = str(Path(pdf_path).relative_to('downloads')) if 'downloads' in pdf_path else pdf_path

                        sibling_data = self._search_in_sibling_documents(
                            solicitud_id=solicitud_id,
                            missing_fields=missing_critical,
                            base_path=base_path
                        )

                        # Sobrescribir solo los campos que estaban vacíos
                        for field in missing_critical:
                            if sibling_data.get(field):
                                data[field] = sibling_data[field]
                                logger.info(f"✅ Campo recuperado de hermano: {field} = {sibling_data[field]}")

                        # Actualizar lista de campos aún faltantes
                        missing_critical = [f for f in critical_fields if not data.get(f)]

                    # Si AÚN faltan campos, intentar OCR (solo si es PDF escaneado)
                    if missing_critical:
                        # Detectar si es PDF escaneado
                        if self._is_scanned_pdf(pdf_path):
                            logger.warning(f"⚠️  PDF escaneado detectado, activando OCR...")
                            ocr_data = self._parse_with_ocr(pdf_path)

                            # Sobrescribir solo los campos que estaban vacíos
                            for field in missing_critical:
                                if ocr_data.get(field):
                                    data[field] = ocr_data[field]
                                    logger.info(f"✅ Campo recuperado con OCR: {field} = {ocr_data[field]}")
                        else:
                            logger.info("  PDF con texto extraíble, OCR no necesario")

                # Agregar metadata del PDF
                data.update(pdf_metadata)

                logger.info(f"✅ Formulario SUCTD parseado: {data.get('nombre_proyecto', 'N/A')}")
                return data

        except Exception as e:
            logger.error(f"❌ Error al parsear SUCTD: {str(e)}", exc_info=True)
            raise

    def _parse_with_pypdf_fallback(self, pdf_path: str) -> Dict[str, Any]:
        """
        Fallback parser usando pypdf para extracción de texto plano.

        Útil cuando pdfplumber detecta tablas pero no puede parsearlas correctamente
        (por ejemplo, cuando todas las celdas están merged en una sola).

        Busca patrones de texto específicos:
        - "Proyecto <nombre>"
        - "Empresa <razón social>"
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

            # Buscar campos con regex

            # Proyecto: "Proyecto XXXXXX SUCTD" o "Proyecto XXXXXX"
            proyecto_match = re.search(r'Proyecto\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-\.]+?)(?:\s+SUCTD|\s+Empresa|\n|$)', full_text, re.IGNORECASE)
            if proyecto_match:
                data['nombre_proyecto'] = proyecto_match.group(1).strip()

            # Empresa: "Empresa XXXXXX"
            empresa_match = re.search(r'Empresa\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.\-,&]+?)(?:\s+\d{2}-\d{2}-\d{4}|\n|$)', full_text, re.IGNORECASE)
            if empresa_match:
                data['razon_social'] = empresa_match.group(1).strip()

            # RUT: Extracción progresiva (estricto → permisivo)
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut

            # Fecha: DD-MM-YYYY
            fecha_match = re.search(r'(\d{2}-\d{2}-\d{4})', full_text)
            if fecha_match:
                data['fecha'] = fecha_match.group(1)

            logger.info(f"✅ Fallback pypdf extrajo: proyecto={data.get('nombre_proyecto', 'N/A')}, empresa={data.get('razon_social', 'N/A')}")

            return data

        except Exception as e:
            logger.error(f"❌ Error en fallback pypdf: {str(e)}")
            return data

    def _search_in_sibling_documents(
        self,
        solicitud_id: int,
        missing_fields: List[str],
        base_path: str
    ) -> Dict[str, Any]:
        """
        Busca campos faltantes en documentos hermanos del mismo solicitud_id.

        Útil para formularios multi-página donde los datos están distribuidos
        entre varios PDFs (ej: "1 de 2", "2 de 2").

        Args:
            solicitud_id: ID de la solicitud
            missing_fields: Lista de campos que faltan
            base_path: Ruta base del documento actual

        Returns:
            Diccionario con campos encontrados en documentos hermanos
        """
        logger.info(f"🔍 Buscando {', '.join(missing_fields)} en documentos hermanos de solicitud {solicitud_id}")

        data = {}

        try:
            from src.iterative_parse import get_db_connection

            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)

            # Buscar otros documentos SUCTD del mismo solicitud_id
            query = """
            SELECT local_path
            FROM documentos
            WHERE solicitud_id = %s
              AND tipo_documento = 'Formulario SUCTD'
              AND downloaded = 1
              AND local_path != %s
            ORDER BY local_path
            """

            cursor.execute(query, (solicitud_id, base_path))
            siblings = cursor.fetchall()

            cursor.close()
            conn.close()

            logger.info(f"  Encontrados {len(siblings)} documentos hermanos")

            # Parsear cada hermano buscando los campos faltantes
            for sibling in siblings:
                sibling_path = Path('downloads') / sibling['local_path']

                if not sibling_path.exists():
                    continue

                logger.info(f"  Parseando: {sibling_path.name}")

                # Usar pypdf para extraer texto del hermano
                reader = PdfReader(str(sibling_path))
                full_text = ''
                for page in reader.pages:
                    full_text += page.extract_text() + '\n'

                # Buscar campos específicos que faltan
                if 'rut' in [f.lower() for f in missing_fields]:
                    # RUT: Extracción progresiva (estricto → permisivo)
                    rut = self._extract_rut_progressive(full_text)
                    if rut:
                        data['rut'] = rut
                        logger.info(f"  ✅ RUT encontrado: {data['rut']}")

                if 'razon_social' in [f.lower() for f in missing_fields]:
                    empresa_match = re.search(r'Empresa\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.\-,&]+?)(?:\s+\d{2}-\d{2}-\d{4}|\n|$)', full_text, re.IGNORECASE)
                    if empresa_match:
                        data['razon_social'] = empresa_match.group(1).strip()
                        logger.info(f"  ✅ Empresa encontrada: {data['razon_social']}")

                if 'nombre_proyecto' in [f.lower() for f in missing_fields]:
                    proyecto_match = re.search(r'Proyecto\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-\.]+?)(?:\s+SUCTD|\s+Empresa|\n|$)', full_text, re.IGNORECASE)
                    if proyecto_match:
                        data['nombre_proyecto'] = proyecto_match.group(1).strip()
                        logger.info(f"  ✅ Proyecto encontrado: {data['nombre_proyecto']}")

                # Si ya encontramos todos los campos, salir
                found_all = all(data.get(f.lower()) for f in missing_fields)
                if found_all:
                    logger.info(f"  ✅ Todos los campos encontrados, deteniendo búsqueda")
                    break

            return data

        except Exception as e:
            logger.error(f"❌ Error buscando en hermanos: {str(e)}")
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
        # Ejemplo: "77116422-6" o "771164226"
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

            # Extraer campos con regex (mismo método que pypdf fallback)

            # Proyecto: "Proyecto XXXXXX"
            proyecto_match = re.search(
                r'Proyecto\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\-\.]+?)(?:\s+SUCTD|\s+Empresa|\n|$)',
                full_text,
                re.IGNORECASE
            )
            if proyecto_match:
                data['nombre_proyecto'] = proyecto_match.group(1).strip()
                logger.info(f"  ✅ OCR - Proyecto: {data['nombre_proyecto']}")

            # Empresa: "Empresa XXXXXX"
            empresa_match = re.search(
                r'Empresa\s+([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑa-záéíóúñ0-9\s\.\-,&]+?)(?:\s+\d{2}-\d{2}-\d{4}|\n|$)',
                full_text,
                re.IGNORECASE
            )
            if empresa_match:
                data['razon_social'] = empresa_match.group(1).strip()
                logger.info(f"  ✅ OCR - Empresa: {data['razon_social']}")

            # RUT: Extracción progresiva (estricto → permisivo)
            rut = self._extract_rut_progressive(full_text)
            if rut:
                data['rut'] = rut
                logger.info(f"  ✅ OCR - RUT: {data['rut']}")

            # Fecha: DD-MM-YYYY
            fecha_match = re.search(r'(\d{2}-\d{2}-\d{4})', full_text)
            if fecha_match:
                data['fecha'] = fecha_match.group(1)

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

    def _parse_table(self, table: list) -> Dict[str, Any]:
        """
        Parsea la tabla extraída del PDF con búsqueda flexible.

        V2.0.0: Busca labels y valores en CUALQUIER columna, no solo posiciones fijas.
        Esto resuelve el problema de PDFs con layouts variables (columnas en diferentes posiciones).

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

            # === SECCIÓN: Antecedentes de la Empresa Solicitante ===

            # Razón Social
            label_idx = self._find_label_idx(clean_row, ["razón social", "razon social"])
            if label_idx >= 0 and "razon_social" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["razon_social"] = value

            # RUT
            label_idx = self._find_label_idx(clean_row, ["rut"])
            if label_idx >= 0 and "rut" not in data:
                # Para RUT, buscar con min_length=1 ya que puede ser corto (ej: "1-9")
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value and ("-" in value or value.isdigit()):
                    data["rut"] = self._normalize_rut(value)

            # Domicilio Legal
            label_idx = self._find_label_idx(clean_row, ["domicilio legal"])
            if label_idx >= 0 and "domicilio_legal" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["domicilio_legal"] = value

            # === SECCIÓN: Representante Legal ===

            # Nombre del Representante Legal
            label_idx = self._find_label_idx(clean_row, ["nombre del representante legal"])
            if label_idx >= 0 and "representante_legal_nombre" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["representante_legal_nombre"] = value

            # Email del Representante Legal (solo si ya tenemos el nombre)
            label_idx = self._find_label_idx(clean_row, ["e-mail"])
            if label_idx >= 0 and "representante_legal_nombre" in data and "representante_legal_email" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value and "@" in value:
                    data["representante_legal_email"] = value

            # Teléfono del Representante Legal
            label_idx = self._find_label_idx(clean_row, ["teléfono", "telefono"])
            if label_idx >= 0 and "representante_legal_nombre" in data and "representante_legal_email" in data and "representante_legal_telefono" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["representante_legal_telefono"] = value

            # === SECCIÓN: Coordinadores de Proyectos ===

            # Primer Coordinador - Nombre
            label_idx = self._find_label_idx(clean_row, ["nombre primer coordinador", "coordinador de proyecto"])
            if label_idx >= 0 and "coordinador_proyecto_1_nombre" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["coordinador_proyecto_1_nombre"] = value
                    self._next_coord = 1

            # Segundo Coordinador - Nombre
            label_idx = self._find_label_idx(clean_row, ["nombre segundo coordinador"])
            if label_idx >= 0 and "coordinador_proyecto_2_nombre" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["coordinador_proyecto_2_nombre"] = value
                    self._next_coord = 2

            # Coordinadores - Emails (context-dependent)
            label_idx = self._find_label_idx(clean_row, ["e-mail primer coordinador"])
            if label_idx >= 0 and "coordinador_proyecto_1_email" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value and "@" in value:
                    data["coordinador_proyecto_1_email"] = value

            label_idx = self._find_label_idx(clean_row, ["e-mail segundo coordinador"])
            if label_idx >= 0 and "coordinador_proyecto_2_email" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value and "@" in value:
                    data["coordinador_proyecto_2_email"] = value

            # Coordinadores - Teléfonos
            label_idx = self._find_label_idx(clean_row, ["teléfono primer coordinador", "telefono primer"])
            if label_idx >= 0 and "coordinador_proyecto_1_telefono" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["coordinador_proyecto_1_telefono"] = value

            label_idx = self._find_label_idx(clean_row, ["teléfono segundo coordinador", "telefono segundo"])
            if label_idx >= 0 and "coordinador_proyecto_2_telefono" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["coordinador_proyecto_2_telefono"] = value

            # === SECCIÓN: Antecedentes del Proyecto ===

            # Nombre del Proyecto
            label_idx = self._find_label_idx(clean_row, ["nombre del proyecto"])
            if label_idx >= 0 and "nombre_proyecto" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=5)
                if value:
                    data["nombre_proyecto"] = value

            # Tipo de Proyecto
            label_idx = self._find_label_idx(clean_row, ["tipo de proyecto", "tipo proyecto"])
            if label_idx >= 0 and "tipo_proyecto" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["tipo_proyecto"] = value

            # Tipo de Tecnología
            label_idx = self._find_label_idx(clean_row, ["tipo de tecnología", "tipo tecnologia"])
            if label_idx >= 0 and "tipo_tecnologia" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["tipo_tecnologia"] = value

            # Potencia Neta de Inyección
            label_idx = self._find_label_idx(clean_row, ["potencia neta solicitada de inyección", "potencia neta de inyeccion"])
            if label_idx >= 0 and "potencia_neta_inyeccion_mw" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["potencia_neta_inyeccion_mw"] = self._parse_decimal(value)

            # Potencia Neta de Retiro
            label_idx = self._find_label_idx(clean_row, ["potencia neta solicitada de retiro", "potencia neta de retiro"])
            if label_idx >= 0 and "potencia_neta_retiro_mw" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["potencia_neta_retiro_mw"] = self._parse_decimal(value)

            # Factor de Potencia Nominal
            label_idx = self._find_label_idx(clean_row, ["factor de potencia nominal"])
            if label_idx >= 0 and "factor_potencia_nominal" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["factor_potencia_nominal"] = self._parse_decimal(value)

            # Modo de Operación Inversores
            label_idx = self._find_label_idx(clean_row, ["modo de operación inversores", "modo de operacion"])
            if label_idx >= 0 and "modo_operacion_inversores" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["modo_operacion_inversores"] = value

            # === SECCIÓN: Parámetros Sistemas de Almacenamiento ===

            # Componente Generación
            label_idx = self._find_label_idx(clean_row, ["componente generación", "componente generacion"])
            if label_idx >= 0 and "componente_generacion" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=2)
                if value:
                    data["componente_generacion"] = value

            # Componente Almacenamiento
            label_idx = self._find_label_idx(clean_row, ["componente de almacenamiento"])
            if label_idx >= 0 and "componente_almacenamiento" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=2)
                if value:
                    data["componente_almacenamiento"] = value

            # Potencia [MW] - Primera aparición (generación)
            label_idx = self._find_label_idx(clean_row, ["potencia [mw]"])
            if label_idx >= 0 and "componente_generacion" in data and "componente_generacion_potencia_mw" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["componente_generacion_potencia_mw"] = self._parse_decimal(value)

            # Potencia [MW] - Segunda aparición (almacenamiento)
            label_idx = self._find_label_idx(clean_row, ["potencia [mw]"])
            if label_idx >= 0 and "componente_almacenamiento" in data and "componente_almacenamiento_potencia_mw" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["componente_almacenamiento_potencia_mw"] = self._parse_decimal(value)

            # Energía [MWh]
            label_idx = self._find_label_idx(clean_row, ["energía [mwh]", "energia [mwh]"])
            if label_idx >= 0 and "componente_almacenamiento_energia_mwh" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["componente_almacenamiento_energia_mwh"] = self._parse_decimal(value)

            # Horas de Almacenamiento
            label_idx = self._find_label_idx(clean_row, ["horas de almacenamiento"])
            if label_idx >= 0 and "componente_almacenamiento_horas" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["componente_almacenamiento_horas"] = self._parse_decimal(value)

            # === SECCIÓN: Ubicación Geográfica del Proyecto ===

            # Coordenadas UTM del Proyecto (primera aparición)
            label_idx = self._find_label_idx(clean_row, ["coordenadas u.t.m.", "coordenadas utm"])
            if label_idx >= 0 and "proyecto_coordenadas_utm_huso" not in data:
                # Buscar huso, este, norte en columnas siguientes
                remaining_cols = clean_row[label_idx + 1:]
                if len(remaining_cols) >= 1:
                    data["proyecto_coordenadas_utm_huso"] = remaining_cols[0] if remaining_cols[0] else None
                if len(remaining_cols) >= 3:
                    data["proyecto_coordenadas_utm_este"] = self._parse_coordinate(remaining_cols[2])
                if len(remaining_cols) >= 5:
                    data["proyecto_coordenadas_utm_norte"] = self._parse_coordinate(remaining_cols[4])

            # Comuna del Proyecto (primera aparición)
            label_idx = self._find_label_idx(clean_row, ["comuna"])
            if label_idx >= 0 and "proyecto_comuna" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["proyecto_comuna"] = value
                    # Buscar región en la misma fila
                    region_idx = self._find_label_idx(clean_row[label_idx:], ["región", "region"])
                    if region_idx >= 0:
                        region_value = self._find_value_in_row(clean_row, label_idx + region_idx, min_length=3)
                        if region_value:
                            data["proyecto_region"] = region_value

            # === SECCIÓN: Antecedentes del Punto de Conexión ===

            # Nombre de la S/E o Línea
            label_idx = self._find_label_idx(clean_row, ["nombre de la s/e", "nombre de la se", "línea de transmisión", "linea de transmision"])
            if label_idx >= 0 and "nombre_se_o_linea" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["nombre_se_o_linea"] = value

            # Tipo de Conexión
            label_idx = self._find_label_idx(clean_row, ["tipo de conexión", "tipo de conexion"])
            if label_idx >= 0 and "tipo_conexion" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["tipo_conexion"] = value

            # Seccionamiento: Distancia
            label_idx = self._find_label_idx(clean_row, ["seccionamiento o derivación", "seccionamiento o derivacion"])
            if label_idx >= 0 and "distanci" in " ".join(clean_row).lower() and "seccionamiento_distancia_km" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["seccionamiento_distancia_km"] = self._parse_decimal(value)

            # Seccionamiento: S/E más cercana
            label_idx = self._find_label_idx(clean_row, ["nombre s/e más cercana", "se mas cercana"])
            if label_idx >= 0 and "seccionamiento_se_cercana" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["seccionamiento_se_cercana"] = value

            # Nivel de Tensión
            label_idx = self._find_label_idx(clean_row, ["nivel de tensión", "nivel de tension"])
            if label_idx >= 0 and "nivel_tension_kv" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["nivel_tension_kv"] = value

            # Paño o Estructura
            label_idx = self._find_label_idx(clean_row, ["paño", "pano", "estructura"])
            if label_idx >= 0 and "pano_o_estructura" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=1)
                if value:
                    data["pano_o_estructura"] = value

            # Fecha Estimada de Construcción
            label_idx = self._find_label_idx(clean_row, ["fecha estimada de declaración en construcción", "fecha estimada de construccion"])
            if label_idx >= 0 and "fecha_estimada_construccion" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=8)
                if value:
                    data["fecha_estimada_construccion"] = self._parse_date(value)

            # Fecha Estimada de Operación
            label_idx = self._find_label_idx(clean_row, ["fecha estimada de entrada en operación", "fecha estimada de operacion"])
            if label_idx >= 0 and "fecha_estimada_operacion" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=8)
                if value:
                    data["fecha_estimada_operacion"] = self._parse_date(value)

            # === SECCIÓN: Ubicación Geográfica del Punto de Conexión ===

            # Coordenadas UTM del Punto de Conexión (segunda aparición)
            label_idx = self._find_label_idx(clean_row, ["coordenadas u.t.m.", "coordenadas utm"])
            if label_idx >= 0 and "proyecto_coordenadas_utm_huso" in data and "conexion_coordenadas_utm_huso" not in data:
                # Buscar huso, este, norte en columnas siguientes
                remaining_cols = clean_row[label_idx + 1:]
                if len(remaining_cols) >= 1:
                    data["conexion_coordenadas_utm_huso"] = remaining_cols[0] if remaining_cols[0] else None
                if len(remaining_cols) >= 3:
                    data["conexion_coordenadas_utm_este"] = self._parse_coordinate(remaining_cols[2])
                if len(remaining_cols) >= 5:
                    data["conexion_coordenadas_utm_norte"] = self._parse_coordinate(remaining_cols[4])

            # Comuna del Punto de Conexión (segunda aparición)
            label_idx = self._find_label_idx(clean_row, ["comuna"])
            if label_idx >= 0 and "proyecto_comuna" in data and "conexion_comuna" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
                    data["conexion_comuna"] = value
                    # Buscar región en la misma fila
                    region_idx = self._find_label_idx(clean_row[label_idx:], ["región", "region"])
                    if region_idx >= 0:
                        region_value = self._find_value_in_row(clean_row, label_idx + region_idx, min_length=3)
                        if region_value:
                            data["conexion_region"] = region_value

            # Información Adicional
            label_idx = self._find_label_idx(clean_row, ["información adicional", "informacion adicional"])
            if label_idx >= 0 and "informacion_adicional" not in data:
                value = self._find_value_in_row(clean_row, label_idx, min_length=3)
                if value:
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


def parse_suctd_pdf(pdf_path: str) -> Dict[str, Any]:
    """
    Función helper para parsear un formulario SUCTD desde PDF.

    Args:
        pdf_path: Ruta al archivo PDF

    Returns:
        Diccionario con datos extraídos
    """
    parser = SUCTDPDFParser()
    return parser.parse(pdf_path)
