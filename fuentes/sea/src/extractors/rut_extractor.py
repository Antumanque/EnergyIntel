"""
Extractor de RUTs desde documentos PDF.

Este módulo proporciona funcionalidades para:
1. Extraer texto de PDFs usando pdftotext
2. Identificar RUTs chilenos con validación de dígito verificador
3. Detectar contexto para identificar tipo de RUT (titular, representante, etc.)
4. Guardar RUTs en la base de datos
"""

import json
import logging
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class RutEncontrado:
    """Representa un RUT encontrado en un documento."""
    rut_formateado: str  # Formato estándar XX.XXX.XXX-X
    rut_normalizado: str  # Sin puntos ni guión (ej: "965057609")
    contexto: str  # Texto alrededor del RUT
    tipo: str  # "titular", "representante", "otro"
    posicion: int  # Posición en el texto

    def to_dict(self) -> dict:
        """Convertir a diccionario para exportar."""
        return asdict(self)


class RutExtractor:
    """
    Extractor de RUTs desde texto y PDFs.

    Implementa el algoritmo módulo 11 para validar RUTs chilenos
    y análisis de contexto para identificar el tipo de RUT.
    """

    # Palabras clave que indican RUT del titular/empresa
    KEYWORDS_TITULAR = [
        'titular', 'proponente', 'razón social', 'razon social',
        'propietario', 'empresa', 'sociedad', 'nombre del titular',
        'datos del titular', 'identificación del titular'
    ]

    # Palabras clave que indican RUT del representante legal
    KEYWORDS_REPRESENTANTE = [
        'representante', 'legal', 'apoderado', 'mandatario',
        'rep. legal', 'representante legal', 'firmante'
    ]

    # Patrones regex para detectar RUTs
    PATRONES_RUT = [
        # Con puntos y guión: 12.345.678-9 o 1.234.567-8
        r'\b(\d{1,2}\.\d{3}\.\d{3}-[\dkK])\b',
        # Solo guión: 12345678-9
        r'\b(\d{7,8}-[\dkK])\b',
    ]

    def __init__(self, timeout: int = 30):
        """
        Inicializar el extractor.

        Args:
            timeout: Timeout para descargas HTTP en segundos
        """
        self.timeout = timeout

    @staticmethod
    def validar_dv(rut: str) -> bool:
        """
        Validar dígito verificador de un RUT chileno.

        Usa el algoritmo módulo 11.

        Args:
            rut: RUT en cualquier formato (con o sin puntos/guión)

        Returns:
            True si el dígito verificador es correcto
        """
        # Limpiar: quitar puntos, guiones, espacios
        rut_limpio = re.sub(r'[.\-\s]', '', rut.upper())

        if len(rut_limpio) < 2:
            return False

        # Separar cuerpo y dígito verificador
        cuerpo = rut_limpio[:-1]
        dv_dado = rut_limpio[-1]

        # Verificar que el cuerpo sea numérico
        if not cuerpo.isdigit():
            return False

        # Calcular dígito verificador con módulo 11
        suma = 0
        multiplicador = 2
        for digito in reversed(cuerpo):
            suma += int(digito) * multiplicador
            multiplicador = multiplicador + 1 if multiplicador < 7 else 2

        resto = suma % 11
        dv_calculado = 11 - resto

        if dv_calculado == 11:
            dv_esperado = '0'
        elif dv_calculado == 10:
            dv_esperado = 'K'
        else:
            dv_esperado = str(dv_calculado)

        return dv_dado == dv_esperado

    @staticmethod
    def normalizar_rut(rut: str) -> str:
        """
        Normalizar RUT quitando puntos y guiones.

        Args:
            rut: RUT en cualquier formato

        Returns:
            RUT sin puntos ni guiones, en mayúsculas
        """
        return re.sub(r'[.\-\s]', '', rut.upper())

    @staticmethod
    def formatear_rut(rut: str) -> str:
        """
        Formatear RUT al formato estándar XX.XXX.XXX-X.

        Args:
            rut: RUT normalizado (sin puntos ni guiones)

        Returns:
            RUT formateado
        """
        rut_limpio = re.sub(r'[.\-\s]', '', rut.upper())
        if len(rut_limpio) < 2:
            return rut

        dv = rut_limpio[-1]
        cuerpo = rut_limpio[:-1]

        # Agregar puntos cada 3 dígitos desde la derecha
        cuerpo_formateado = ''
        for i, digito in enumerate(reversed(cuerpo)):
            if i > 0 and i % 3 == 0:
                cuerpo_formateado = '.' + cuerpo_formateado
            cuerpo_formateado = digito + cuerpo_formateado

        return f"{cuerpo_formateado}-{dv}"

    def extraer_texto_pdf(self, pdf_path: str) -> Optional[str]:
        """
        Extraer texto de un archivo PDF usando pdftotext.

        Args:
            pdf_path: Ruta al archivo PDF

        Returns:
            Texto extraído o None si falla
        """
        try:
            result = subprocess.run(
                ['pdftotext', '-layout', pdf_path, '-'],
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            if result.returncode == 0:
                return result.stdout
            else:
                logger.warning(f"pdftotext error: {result.stderr}")
                return None
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout extrayendo texto de {pdf_path}")
            return None
        except FileNotFoundError:
            logger.error("pdftotext no está instalado. Instalar con: pacman -S poppler")
            return None
        except Exception as e:
            logger.error(f"Error extrayendo texto: {e}")
            return None

    def descargar_pdf(self, url: str) -> Optional[str]:
        """
        Descargar PDF desde URL a archivo temporal.

        Args:
            url: URL del PDF

        Returns:
            Ruta al archivo temporal o None si falla
        """
        try:
            response = httpx.get(url, timeout=self.timeout, follow_redirects=True)
            if response.status_code == 200:
                # Crear archivo temporal
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
                    f.write(response.content)
                    return f.name
            else:
                logger.warning(f"HTTP {response.status_code} descargando {url}")
                return None
        except Exception as e:
            logger.error(f"Error descargando PDF: {e}")
            return None

    def _detectar_contexto(self, texto: str, posicion: int, ventana: int = 150) -> str:
        """
        Obtener contexto alrededor de una posición en el texto.

        Args:
            texto: Texto completo
            posicion: Posición del RUT
            ventana: Caracteres antes y después

        Returns:
            Contexto limpio
        """
        start = max(0, posicion - ventana)
        end = min(len(texto), posicion + ventana)
        contexto = texto[start:end]
        # Limpiar saltos de línea múltiples
        contexto = re.sub(r'\s+', ' ', contexto)
        return contexto.strip()

    def _clasificar_tipo(self, contexto: str) -> str:
        """Clasificar el tipo de RUT según su contexto."""
        contexto_lower = contexto.lower()

        # Primero verificar representante (más específico)
        if any(kw in contexto_lower for kw in self.KEYWORDS_REPRESENTANTE):
            return "representante"

        # Luego titular
        if any(kw in contexto_lower for kw in self.KEYWORDS_TITULAR):
            return "titular"

        return "otro"

    def extraer_ruts(self, texto: str) -> list[RutEncontrado]:
        """
        Extraer todos los RUTs de un texto con validación y contexto.

        Args:
            texto: Texto donde buscar RUTs

        Returns:
            Lista de RUTs encontrados (solo válidos)
        """
        resultados = []
        ruts_vistos = set()

        for patron in self.PATRONES_RUT:
            for match in re.finditer(patron, texto, re.IGNORECASE):
                rut = match.group(1)
                rut_normalizado = self.normalizar_rut(rut)

                # Evitar duplicados
                if rut_normalizado in ruts_vistos:
                    continue

                # Validar longitud razonable
                if not (7 <= len(rut_normalizado) <= 10):
                    continue

                # Validar dígito verificador
                if not self.validar_dv(rut):
                    continue

                ruts_vistos.add(rut_normalizado)

                # Obtener y analizar contexto
                contexto = self._detectar_contexto(texto, match.start())
                tipo = self._clasificar_tipo(contexto)

                resultados.append(RutEncontrado(
                    rut_formateado=self.formatear_rut(rut_normalizado),
                    rut_normalizado=rut_normalizado,
                    contexto=contexto,
                    tipo=tipo,
                    posicion=match.start()
                ))

        # Ordenar por posición en el documento
        resultados.sort(key=lambda r: r.posicion)

        return resultados

    def identificar_rut_titular(self, ruts: list[RutEncontrado]) -> Optional[RutEncontrado]:
        """
        Identificar el RUT más probable del titular entre los encontrados.

        Prioriza:
        1. RUT con contexto explícito de "titular"
        2. RUT de empresa (empieza con 7X, 8X, 9X) que no sea representante
        3. Primer RUT encontrado que no sea representante

        Args:
            ruts: Lista de RUTs encontrados

        Returns:
            RUT del titular o None
        """
        if not ruts:
            return None

        # Prioridad 1: RUT con tipo explícito "titular"
        titulares = [r for r in ruts if r.tipo == "titular"]
        if titulares:
            return titulares[0]

        # Prioridad 2: RUT de empresa (7X, 8X, 9X millones) que no sea representante
        empresas = [
            r for r in ruts
            if r.rut_normalizado[0] in '789'
            and len(r.rut_normalizado) >= 9
            and r.tipo != "representante"
        ]
        if empresas:
            return empresas[0]

        # Prioridad 3: Cualquier RUT que no sea representante
        no_representantes = [r for r in ruts if r.tipo != "representante"]
        if no_representantes:
            return no_representantes[0]

        # Último recurso: primer RUT
        return ruts[0]

    def extraer_ruts_desde_url(self, pdf_url: str) -> tuple[list[RutEncontrado], Optional[str]]:
        """
        Descargar PDF desde URL y extraer todos los RUTs.

        Args:
            pdf_url: URL del PDF

        Returns:
            Tupla (lista de RUTs, error o None)
        """
        # Descargar PDF
        pdf_path = self.descargar_pdf(pdf_url)
        if not pdf_path:
            return [], "Error descargando PDF"

        try:
            # Extraer texto
            texto = self.extraer_texto_pdf(pdf_path)
            if not texto:
                return [], "Error extrayendo texto del PDF"

            # Extraer todos los RUTs
            return self.extraer_ruts(texto), None
        finally:
            # Limpiar archivo temporal
            try:
                Path(pdf_path).unlink()
            except Exception:
                pass


def get_rut_extractor(timeout: int = 30) -> RutExtractor:
    """
    Factory function para crear un RutExtractor.

    Args:
        timeout: Timeout para operaciones HTTP

    Returns:
        Instancia de RutExtractor
    """
    return RutExtractor(timeout=timeout)


def extraer_y_guardar_ruts(link_id: int, pdf_url: str, cursor, extractor: Optional[RutExtractor] = None) -> bool:
    """
    Extraer RUTs de un PDF y guardarlos en la base de datos.

    Args:
        link_id: ID del registro en resumen_ejecutivo_links
        pdf_url: URL del PDF
        cursor: Cursor de base de datos
        extractor: Instancia de RutExtractor (opcional)

    Returns:
        True si se extrajeron RUTs exitosamente
    """
    if extractor is None:
        extractor = get_rut_extractor()

    ruts, error = extractor.extraer_ruts_desde_url(pdf_url)

    if error:
        logger.warning(f"Error extrayendo RUTs de link {link_id}: {error}")
        # Actualizar con error pero sin RUTs
        cursor.execute("""
            UPDATE resumen_ejecutivo_links
            SET ruts_extracted_at = %s, ruts_json = %s
            WHERE id = %s
        """, (datetime.now(), json.dumps({"error": error}), link_id))
        return False

    # Preparar datos para guardar
    rut_1 = ruts[0].rut_formateado if len(ruts) > 0 else None
    rut_2 = ruts[1].rut_formateado if len(ruts) > 1 else None
    rut_3 = ruts[2].rut_formateado if len(ruts) > 2 else None

    # JSON con todos los RUTs y contextos
    ruts_json = {
        "total": len(ruts),
        "ruts": [r.to_dict() for r in ruts]
    }

    # Identificar el RUT del titular
    rut_titular = extractor.identificar_rut_titular(ruts)
    if rut_titular:
        ruts_json["rut_titular"] = rut_titular.rut_formateado

    # Guardar en BD
    cursor.execute("""
        UPDATE resumen_ejecutivo_links
        SET rut_1 = %s, rut_2 = %s, rut_3 = %s,
            ruts_json = %s, ruts_extracted_at = %s
        WHERE id = %s
    """, (rut_1, rut_2, rut_3, json.dumps(ruts_json, ensure_ascii=False), datetime.now(), link_id))

    return len(ruts) > 0
