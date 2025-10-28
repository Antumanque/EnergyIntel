#!/usr/bin/env python3
"""
Script para diagnosticar por qué el parser SUCTD falla con el PDF de Illimani.
"""

import pdfplumber
from pathlib import Path

pdf_path = Path("downloads/2752/2504-FORM-SUCTD-V1.pdf")

print("=" * 80)
print("DIAGNÓSTICO: Parser SUCTD - Parque CRCA Illimani")
print("=" * 80)
print()

with pdfplumber.open(pdf_path) as pdf:
    print(f"Total páginas: {len(pdf.pages)}")
    print()

    # Procesar primera página
    page = pdf.pages[0]
    tables = page.extract_tables()

    print(f"Tablas encontradas en página 1: {len(tables)}")
    print()

    if tables:
        table = tables[0]
        print(f"Primera tabla tiene {len(table)} filas")
        print()

        # Mostrar primeras 20 filas para ver la estructura
        print("ESTRUCTURA DE LA TABLA (primeras 20 filas):")
        print("-" * 80)

        for i, row in enumerate(table[:20], 1):
            print(f"\nFila {i} (columnas: {len(row)}):")
            for col_idx, cell in enumerate(row):
                cell_str = str(cell).strip() if cell else ""
                if cell_str:  # Solo mostrar celdas con contenido
                    print(f"  [{col_idx}] = {cell_str[:60]}")

        print()
        print("=" * 80)
        print("BUSCANDO CAMPOS CRÍTICOS:")
        print("=" * 80)

        # Buscar los campos que el parser dice que faltan
        found_razon = False
        found_rut = False
        found_nombre = False

        for i, row in enumerate(table, 1):
            clean_row = [str(cell).strip() if cell else "" for cell in row]

            # Buscar en todas las columnas
            for col_idx, cell in enumerate(clean_row):
                cell_lower = cell.lower()

                # Razón Social
                if not found_razon and ("razón social" in cell_lower or "razon social" in cell_lower):
                    print(f"\n✓ 'Razón Social' encontrada en:")
                    print(f"  Fila {i}, Columna [{col_idx}]: '{cell}'")
                    print(f"  Fila completa: {clean_row}")
                    found_razon = True

                # RUT
                if not found_rut and cell_lower == "rut":
                    print(f"\n✓ 'RUT' encontrado en:")
                    print(f"  Fila {i}, Columna [{col_idx}]: '{cell}'")
                    print(f"  Fila completa: {clean_row}")
                    found_rut = True

                # Nombre del Proyecto
                if not found_nombre and "nombre del proyecto" in cell_lower:
                    print(f"\n✓ 'Nombre del Proyecto' encontrado en:")
                    print(f"  Fila {i}, Columna [{col_idx}]: '{cell}'")
                    print(f"  Fila completa: {clean_row}")
                    found_nombre = True

        print()
        print("=" * 80)
        print("RESUMEN:")
        print("=" * 80)
        print(f"Razón Social encontrada: {'✓ SÍ' if found_razon else '✗ NO'}")
        print(f"RUT encontrado: {'✓ SÍ' if found_rut else '✗ NO'}")
        print(f"Nombre del Proyecto encontrado: {'✓ SÍ' if found_nombre else '✗ NO'}")
        print()

        # Mostrar qué hace el parser actual
        print("=" * 80)
        print("SIMULACIÓN DEL PARSER ACTUAL:")
        print("=" * 80)
        print("El parser busca en posiciones:")
        print("  label = clean_row[1]")
        print("  value = clean_row[2]")
        print()

        for i, row in enumerate(table[:15], 1):
            clean_row = [str(cell).strip() if cell else "" for cell in row]
            if len(clean_row) > 2:
                label = clean_row[1].lower() if len(clean_row) > 1 else ""
                value = clean_row[2] if len(clean_row) > 2 else ""

                # Solo mostrar si el label contiene algo relevante
                if any(keyword in label for keyword in ["razón", "razon", "rut", "nombre", "proyecto"]):
                    print(f"Fila {i}:")
                    print(f"  Label (col[1]): '{clean_row[1] if len(clean_row) > 1 else ''}'")
                    print(f"  Value (col[2]): '{value}'")
                    print()

print("\nFIN DEL DIAGNÓSTICO")
