#!/usr/bin/env python3
"""
Test del parser v2.0.0 con el PDF de Parque CRCA illimani.
Este PDF antes fallaba porque los valores estaban en columna [6] en vez de [2].
"""

from pathlib import Path
from src.parsers.pdf_suctd import SUCTDPDFParser

pdf_path = Path("downloads/2752/2504-FORM-SUCTD-V1.pdf")

print("=" * 80)
print("TEST: Parser SUCTD v2.0.0 - Parque CRCA Illimani")
print("=" * 80)
print()

parser = SUCTDPDFParser()
print(f"Parser Version: {parser.version}")
print()

try:
    data = parser.parse(str(pdf_path))

    print("✅ PARSING EXITOSO!")
    print()

    # Verificar los 3 campos críticos que antes fallaban
    print("CAMPOS CRÍTICOS:")
    print("-" * 80)
    print(f"Razón Social: {data.get('razon_social', '❌ NO ENCONTRADO')}")
    print(f"RUT: {data.get('rut', '❌ NO ENCONTRADO')}")
    print(f"Nombre Proyecto: {data.get('nombre_proyecto', '❌ NO ENCONTRADO')}")
    print()

    # Verificar otros campos importantes
    print("OTROS CAMPOS:")
    print("-" * 80)
    print(f"Domicilio Legal: {data.get('domicilio_legal', 'N/A')}")
    print(f"Tipo Proyecto: {data.get('tipo_proyecto', 'N/A')}")
    print(f"Tipo Tecnología: {data.get('tipo_tecnologia', 'N/A')}")
    print(f"Potencia Inyección: {data.get('potencia_neta_inyeccion_mw', 'N/A')} MW")
    print(f"Comuna: {data.get('proyecto_comuna', 'N/A')}")
    print(f"Región: {data.get('proyecto_region', 'N/A')}")
    print()

    # Contar campos extraídos
    total_campos = len([v for v in data.values() if v is not None and v != ""])
    print(f"Total campos extraídos: {total_campos}")
    print()

    # Verificar si cumple con requisitos mínimos
    campos_criticos = ["razon_social", "rut", "nombre_proyecto"]
    campos_faltantes = [c for c in campos_criticos if not data.get(c)]

    if campos_faltantes:
        print(f"❌ CAMPOS CRÍTICOS FALTANTES: {', '.join(campos_faltantes)}")
    else:
        print("✅ TODOS LOS CAMPOS CRÍTICOS PRESENTES")

except Exception as e:
    print(f"❌ ERROR AL PARSEAR: {str(e)}")
    import traceback
    traceback.print_exc()

print()
print("=" * 80)
