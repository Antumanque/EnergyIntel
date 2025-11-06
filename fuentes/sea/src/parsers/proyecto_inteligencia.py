"""
Parser de inteligencia de negocio usando Claude CLI.

Este módulo analiza el texto extraído de PDFs de Resumen Ejecutivo
para identificar industria, oportunidades de negocio, y datos clave.
"""

import json
import logging
import subprocess
from typing import Any

logger = logging.getLogger(__name__)


class ProyectoInteligenciaParser:
    """
    Parser que usa Claude CLI (Haiku 4.5) para extraer inteligencia de negocio.
    """

    def __init__(self):
        """
        Inicializar parser.
        """
        self.model = "haiku"  # Claude Haiku 4.5

    def parse_proyecto_intelligence(
        self, pdf_text: str, id_documento: int
    ) -> dict[str, Any]:
        """
        Analizar texto del PDF y extraer inteligencia de negocio usando Claude CLI.

        Args:
            pdf_text: Texto completo extraído del PDF
            id_documento: ID del documento

        Returns:
            Diccionario con inteligencia extraída o error
        """
        if not pdf_text or len(pdf_text.strip()) < 100:
            return {
                "id_documento": id_documento,
                "status": "error",
                "error_message": "Texto del PDF vacío o muy corto",
            }

        try:
            # Construir prompt
            prompt = self._build_prompt(pdf_text)

            # Llamar a Claude CLI
            result = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--model", self.model,
                    "--output-format", "text",
                    prompt
                ],
                capture_output=True,
                text=True,
                timeout=60  # 60 segundos timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr or "Error desconocido"
                logger.error(f"Error ejecutando Claude CLI para documento {id_documento}: {error_msg}")
                return {
                    "id_documento": id_documento,
                    "status": "error",
                    "error_message": f"Error de Claude CLI: {error_msg[:200]}",
                }

            # Parsear respuesta JSON
            respuesta_texto = result.stdout.strip()

            # Claude CLI puede agregar texto antes/después del JSON, buscar el JSON
            try:
                # Buscar el primer { y el último }
                start = respuesta_texto.find('{')
                end = respuesta_texto.rfind('}')
                if start != -1 and end != -1:
                    json_str = respuesta_texto[start:end+1]
                    datos = json.loads(json_str)
                else:
                    raise json.JSONDecodeError("No se encontró JSON en respuesta", respuesta_texto, 0)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Respuesta de Claude no es JSON válido para documento {id_documento}: {e}"
                )
                return {
                    "id_documento": id_documento,
                    "status": "error",
                    "error_message": "Respuesta de Claude no es JSON válido",
                    "raw_response": respuesta_texto[:500],
                }

            # Validar estructura de respuesta
            if not all(k in datos for k in ["industria", "es_energia"]):
                return {
                    "id_documento": id_documento,
                    "status": "error",
                    "error_message": "Respuesta incompleta de Claude",
                    "raw_response": respuesta_texto[:500],
                }

            # Construir resultado
            return {
                "id_documento": id_documento,
                "industria": datos["industria"],
                "es_energia": bool(datos["es_energia"]),
                "sub_industria": datos.get("sub_industria"),
                "ubicacion_geografica": datos.get("ubicacion_geografica"),
                "capacidad_electrica": datos.get("capacidad_electrica"),
                "capacidad_termica": datos.get("capacidad_termica"),
                "requerimientos_infraestructura": datos.get("requerimientos_infraestructura"),
                "requerimientos_ingenieria": datos.get("requerimientos_ingenieria"),
                "oportunidad_negocio": datos.get("oportunidad_negocio"),
                "datos_clave": json.dumps(datos.get("datos_clave", {})),
                "modelo_usado": "claude-haiku-4-5",
                "pdf_text_length": len(pdf_text),
                "status": "completed",
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout ejecutando Claude CLI para documento {id_documento}")
            return {
                "id_documento": id_documento,
                "status": "error",
                "error_message": "Timeout (>60s) esperando respuesta de Claude",
            }
        except Exception as e:
            logger.error(
                f"Error parseando inteligencia de documento {id_documento}: {e}",
                exc_info=True,
            )
            return {
                "id_documento": id_documento,
                "status": "error",
                "error_message": f"Excepción: {str(e)}",
            }

    def _build_prompt(self, pdf_text: str) -> str:
        """
        Construir prompt para Claude.

        Args:
            pdf_text: Texto del PDF

        Returns:
            Prompt completo
        """
        # Limitar texto si es muy largo
        max_chars = 50000  # ~12,500 tokens aproximadamente
        if len(pdf_text) > max_chars:
            pdf_text = pdf_text[:max_chars] + "\n\n[... texto truncado ...]"

        prompt = f"""Eres un analista de inteligencia de negocios especializado en proyectos ambientales e industriales de Chile, con enfoque en oportunidades de ingeniería y construcción.

Analiza el siguiente Resumen Ejecutivo de un proyecto y extrae información técnica detallada:

1. **industria**: Categoría principal del proyecto. Usa SOLO una de estas:
   - energia (proyectos de energía: solar, eólica, hidroeléctrica, térmica, baterías, etc.)
   - mineria (proyectos mineros: extracción, procesamiento)
   - construccion (infraestructura, edificios, carreteras)
   - agricultura (proyectos agrícolas, ganaderos, forestales)
   - industrial (plantas industriales, manufactura)
   - acuicultura (cultivos acuáticos, pisciculturas)
   - residuos (gestión de residuos, rellenos sanitarios)
   - transporte (puertos, aeropuertos, terminales)
   - agua (plantas de tratamiento, desalinización)
   - otro (si no calza en ninguna categoría)

2. **es_energia**: true o false - ¿Es del sector energía?

3. **sub_industria**: Sub-categoría específica (ej: "solar fotovoltaica con almacenamiento BESS", "minería de cobre", "planta desalinizadora")

4. **ubicacion_geografica**: Ubicación completa y detallada:
   - Región, provincia, comuna
   - Coordenadas si están disponibles
   - Descripción del sitio (ej: "Km 45 Ruta 5 Norte")

5. **capacidad_electrica**: Solo para proyectos de energía:
   - Potencia instalada (MW, MWp, kW)
   - Potencia de inyección (MWn)
   - Generación esperada (GWh/año)
   - Si no aplica, dejar null

6. **capacidad_termica**: Solo para proyectos con componente térmico:
   - Capacidad térmica en MW térmico
   - Si no aplica, dejar null

7. **requerimientos_infraestructura**: Lista detallada de infraestructura necesaria:
   - Líneas de transmisión/distribución (longitud, voltaje)
   - Subestaciones eléctricas
   - Caminos de acceso (longitud, especificaciones)
   - Sistemas de agua (caudal, fuente)
   - Instalaciones portuarias si aplica
   - Edificaciones necesarias
   - Menciona cantidades y especificaciones técnicas

8. **requerimientos_ingenieria**: Servicios de ingeniería y consultoría requeridos:
   - Estudios ambientales necesarios
   - Diseño de ingeniería (eléctrica, civil, mecánica)
   - Estudios geotécnicos
   - Estudios de interconexión
   - Permisos y tramitaciones
   - Supervisión de obras
   - Menciona fase y alcance

9. **oportunidad_negocio**: Análisis enfocado en oportunidades (2-3 oraciones):
   - Inversión estimada
   - Equipamiento principal requerido (fabricantes potenciales)
   - Servicios de construcción y montaje necesarios
   - Oportunidades de suministro (materiales, equipos)

10. **datos_clave**: Objeto JSON con datos técnicos adicionales relevantes

IMPORTANTE:
- Responde SOLO con JSON válido, sin texto adicional
- Si un campo no aplica al tipo de proyecto (ej: capacidad_termica en proyecto solar), usa null
- Si no encuentras información específica para un campo relevante, usa el string "No se encuentra información"
- No inventes ni inferir datos - solo extrae lo que está explícitamente en el documento

{{
  "industria": "energia",
  "es_energia": true,
  "sub_industria": "solar fotovoltaica con BESS",
  "ubicacion_geografica": "Región de Atacama, Comuna de Diego de Almagro, coordenadas -26.xxx, -69.xxx",
  "capacidad_electrica": "150 MWp instalado / 55 MWn inyección / 250 GWh/año",
  "capacidad_termica": null,
  "requerimientos_infraestructura": "Línea transmisión 6.86 km a 110 kV hacia SE BESS Halcón 10. Camino acceso 2 km (mejoramiento ruta existente). Sistema agua 15 m³/día desde pozo. Subestación elevadora 33/110 kV. 38 centros de transformación. Edificio O&M 200 m².",
  "requerimientos_ingenieria": "Estudio impacto ambiental (DIA). Ingeniería de detalle eléctrica y civil. Estudio interconexión al SEN. Estudios geotécnicos para fundaciones. Diseño sistema BESS. Supervisión construcción y puesta en marcha. Tramitación permisos sectoriales.",
  "oportunidad_negocio": "Inversión estimada >USD 100M. Requiere 90,720 paneles monocristalinos 710W, 285 inversores, 58 contenedores baterías litio (458 MWh). Oportunidad para proveedores equipamiento eléctrico, empresas EPC, servicios montaje y O&M.",
  "datos_clave": {{
    "inversion_usd": 100000000,
    "paneles": 90720,
    "inversores": 285,
    "almacenamiento_mwh": 458,
    "area_hectareas": 153,
    "vida_util_anos": 30,
    "inicio_construccion": "H1 2027",
    "inicio_operacion": "H2 2028"
  }}
}}

TEXTO DEL RESUMEN EJECUTIVO:

{pdf_text}
"""
        return prompt


def get_proyecto_inteligencia_parser() -> ProyectoInteligenciaParser:
    """
    Factory function para crear parser de inteligencia.

    Returns:
        Instancia de ProyectoInteligenciaParser
    """
    return ProyectoInteligenciaParser()
