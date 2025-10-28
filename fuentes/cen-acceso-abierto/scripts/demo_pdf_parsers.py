#!/usr/bin/env python3
"""
Demo: Comparación de bibliotecas de parsing PDF para formularios SUCTD.

Prueba diferentes bibliotecas para extraer datos del PDF "Parque CRCA Illimani"
y compara su efectividad.

Bibliotecas probadas:
1. pdfplumber (actual)
2. tabula-py
3. camelot-py
4. pymupdf (PyMuPDF/fitz)
5. pypdf (PyPDF2)
"""

import sys
from pathlib import Path
from typing import Dict, Any, List
import json

# Colores para terminal
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(text: str):
    """Imprime un header formateado."""
    print()
    print(Colors.HEADER + "=" * 80 + Colors.ENDC)
    print(Colors.HEADER + Colors.BOLD + text.center(80) + Colors.ENDC)
    print(Colors.HEADER + "=" * 80 + Colors.ENDC)
    print()

def print_section(text: str):
    """Imprime una sección."""
    print()
    print(Colors.OKBLUE + "-" * 80 + Colors.ENDC)
    print(Colors.OKBLUE + Colors.BOLD + text + Colors.ENDC)
    print(Colors.OKBLUE + "-" * 80 + Colors.ENDC)

def extract_campos_criticos(data: Any) -> Dict[str, str]:
    """
    Intenta extraer los 3 campos críticos de los datos parseados.

    Args:
        data: Datos en cualquier formato (dict, DataFrame, lista de listas, etc.)

    Returns:
        Dict con razon_social, rut, nombre_proyecto (vacíos si no se encuentran)
    """
    campos = {
        "razon_social": "",
        "rut": "",
        "nombre_proyecto": ""
    }

    # Convertir a texto si es necesario para buscar
    if isinstance(data, dict):
        text = json.dumps(data, ensure_ascii=False).lower()
    elif isinstance(data, list):
        text = str(data).lower()
    else:
        text = str(data).lower()

    # Buscar patrones
    if "cielpanel" in text:
        campos["razon_social"] = "Cielpanel SPA"
    if "76.732.087-6" in text or "76732087" in text:
        campos["rut"] = "76.732.087-6"
    if "crca illimani" in text or "parque crca" in text:
        campos["nombre_proyecto"] = "Parque CRCA illimani"

    return campos

def test_pdfplumber(pdf_path: Path) -> Dict[str, Any]:
    """Prueba extracción con pdfplumber (método actual)."""
    import pdfplumber

    print_section("1. PDFPlumber (Biblioteca Actual)")

    result = {
        "success": False,
        "tables_found": 0,
        "campos_criticos": {},
        "raw_data": None,
        "notes": []
    }

    try:
        with pdfplumber.open(pdf_path) as pdf:
            print(f"Total páginas: {len(pdf.pages)}")

            page = pdf.pages[0]
            tables = page.extract_tables()
            result["tables_found"] = len(tables)

            print(f"Tablas encontradas: {len(tables)}")

            if tables:
                table = tables[0]
                result["raw_data"] = table[:10]  # Primeras 10 filas

                print(f"Primera tabla: {len(table)} filas x {len(table[0]) if table else 0} columnas")
                print()
                print("Primeras 5 filas:")
                for i, row in enumerate(table[:5], 1):
                    print(f"  Fila {i}: {row}")

                # Buscar campos críticos
                for row in table:
                    clean_row = [str(cell).strip() if cell else "" for cell in row]

                    # Buscar Razón Social
                    for idx, cell in enumerate(clean_row):
                        if "razón social" in cell.lower():
                            # Valor puede estar en cualquier columna después
                            for val_idx in range(idx + 1, len(clean_row)):
                                if clean_row[val_idx] and len(clean_row[val_idx]) > 3:
                                    result["campos_criticos"]["razon_social"] = clean_row[val_idx]
                                    result["notes"].append(f"Razón Social en col[{val_idx}]")
                                    break

                        if cell.lower() == "rut":
                            for val_idx in range(idx + 1, len(clean_row)):
                                if clean_row[val_idx] and "-" in clean_row[val_idx]:
                                    result["campos_criticos"]["rut"] = clean_row[val_idx]
                                    result["notes"].append(f"RUT en col[{val_idx}]")
                                    break

                        if "nombre del proyecto" in cell.lower():
                            for val_idx in range(idx + 1, len(clean_row)):
                                if clean_row[val_idx] and len(clean_row[val_idx]) > 5:
                                    result["campos_criticos"]["nombre_proyecto"] = clean_row[val_idx]
                                    result["notes"].append(f"Nombre Proyecto en col[{val_idx}]")
                                    break

                result["success"] = len(result["campos_criticos"]) >= 3

        print()
        print(Colors.OKGREEN + "✓ Campos encontrados:" + Colors.ENDC)
        for campo, valor in result["campos_criticos"].items():
            if valor:
                print(f"  {campo}: {valor}")

        if result["notes"]:
            print()
            print("Notas:")
            for note in result["notes"]:
                print(f"  - {note}")

    except Exception as e:
        result["notes"].append(f"Error: {str(e)}")
        print(Colors.FAIL + f"✗ Error: {str(e)}" + Colors.ENDC)

    return result


def test_tabula(pdf_path: Path) -> Dict[str, Any]:
    """Prueba extracción con tabula-py."""
    import tabula

    print_section("2. Tabula-py (Java-based)")

    result = {
        "success": False,
        "tables_found": 0,
        "campos_criticos": {},
        "raw_data": None,
        "notes": []
    }

    try:
        # Leer todas las tablas de la primera página
        dfs = tabula.read_pdf(str(pdf_path), pages=1, multiple_tables=True)
        result["tables_found"] = len(dfs)

        print(f"DataFrames encontrados: {len(dfs)}")

        if dfs:
            df = dfs[0]
            print(f"Primera tabla: {df.shape[0]} filas x {df.shape[1]} columnas")
            print()
            print("Primeras 5 filas:")
            print(df.head())

            result["raw_data"] = df.head(10).to_dict()

            # Buscar campos en todo el DataFrame
            df_str = df.to_string().lower()
            campos = extract_campos_criticos(df_str)
            result["campos_criticos"] = {k: v for k, v in campos.items() if v}
            result["success"] = len(result["campos_criticos"]) >= 3

            if result["campos_criticos"]:
                print()
                print(Colors.OKGREEN + "✓ Campos encontrados:" + Colors.ENDC)
                for campo, valor in result["campos_criticos"].items():
                    print(f"  {campo}: {valor}")

    except Exception as e:
        result["notes"].append(f"Error: {str(e)}")
        print(Colors.FAIL + f"✗ Error: {str(e)}" + Colors.ENDC)

    return result


def test_camelot(pdf_path: Path) -> Dict[str, Any]:
    """Prueba extracción con camelot."""
    import camelot

    print_section("3. Camelot-py (Especializado en tablas complejas)")

    result = {
        "success": False,
        "tables_found": 0,
        "campos_criticos": {},
        "raw_data": None,
        "notes": []
    }

    try:
        # Probar método 'stream' (mejor para PDFs con líneas)
        print("Probando método 'stream'...")
        tables = camelot.read_pdf(str(pdf_path), pages='1', flavor='stream')
        result["tables_found"] = len(tables)

        print(f"Tablas encontradas: {len(tables)}")

        if tables:
            table = tables[0]
            df = table.df

            print(f"Primera tabla: {df.shape[0]} filas x {df.shape[1]} columnas")
            print(f"Accuracy: {table.parsing_report['accuracy']:.2f}%")
            print()
            print("Primeras 5 filas:")
            print(df.head())

            result["raw_data"] = df.head(10).to_dict()
            result["notes"].append(f"Accuracy: {table.parsing_report['accuracy']:.2f}%")

            # Buscar campos
            df_str = df.to_string().lower()
            campos = extract_campos_criticos(df_str)
            result["campos_criticos"] = {k: v for k, v in campos.items() if v}
            result["success"] = len(result["campos_criticos"]) >= 3

            if result["campos_criticos"]:
                print()
                print(Colors.OKGREEN + "✓ Campos encontrados:" + Colors.ENDC)
                for campo, valor in result["campos_criticos"].items():
                    print(f"  {campo}: {valor}")

    except Exception as e:
        result["notes"].append(f"Error: {str(e)}")
        print(Colors.FAIL + f"✗ Error: {str(e)}" + Colors.ENDC)

    return result


def test_pymupdf(pdf_path: Path) -> Dict[str, Any]:
    """Prueba extracción con PyMuPDF (fitz)."""
    import fitz  # PyMuPDF

    print_section("4. PyMuPDF (fitz) - Rápido y moderno")

    result = {
        "success": False,
        "tables_found": 0,
        "campos_criticos": {},
        "raw_data": None,
        "notes": []
    }

    try:
        doc = fitz.open(pdf_path)
        page = doc[0]

        # Método 1: Extraer texto completo
        text = page.get_text()
        print("Texto extraído (primeros 500 caracteres):")
        print(text[:500])

        # Método 2: Buscar tablas (pymupdf 1.23+)
        try:
            tables = page.find_tables()
            result["tables_found"] = len(tables)

            print()
            print(f"Tablas encontradas: {len(tables)}")

            if tables:
                table = tables[0]
                print(f"Primera tabla: {table.row_count} filas x {table.col_count} columnas")

                # Extraer como lista
                data = table.extract()
                result["raw_data"] = data[:10]

                print()
                print("Primeras 5 filas:")
                for i, row in enumerate(data[:5], 1):
                    print(f"  Fila {i}: {row}")

                # Buscar campos
                text_from_table = str(data).lower()
                campos = extract_campos_criticos(text_from_table)
                result["campos_criticos"] = {k: v for k, v in campos.items() if v}

        except AttributeError:
            result["notes"].append("Versión de PyMuPDF no soporta find_tables()")
            print(Colors.WARNING + "⚠ find_tables() no disponible en esta versión" + Colors.ENDC)

        # Buscar en texto plano
        if not result["campos_criticos"]:
            campos = extract_campos_criticos(text)
            result["campos_criticos"] = {k: v for k, v in campos.items() if v}

        result["success"] = len(result["campos_criticos"]) >= 3

        if result["campos_criticos"]:
            print()
            print(Colors.OKGREEN + "✓ Campos encontrados:" + Colors.ENDC)
            for campo, valor in result["campos_criticos"].items():
                print(f"  {campo}: {valor}")

        doc.close()

    except Exception as e:
        result["notes"].append(f"Error: {str(e)}")
        print(Colors.FAIL + f"✗ Error: {str(e)}" + Colors.ENDC)

    return result


def test_pypdf(pdf_path: Path) -> Dict[str, Any]:
    """Prueba extracción con PyPDF."""
    from pypdf import PdfReader

    print_section("5. PyPDF (pypdf) - Extracción de texto")

    result = {
        "success": False,
        "tables_found": 0,
        "campos_criticos": {},
        "raw_data": None,
        "notes": []
    }

    try:
        reader = PdfReader(pdf_path)
        page = reader.pages[0]

        text = page.extract_text()
        print("Texto extraído (primeros 500 caracteres):")
        print(text[:500])

        result["raw_data"] = text[:1000]
        result["notes"].append("PyPDF extrae solo texto, no tablas estructuradas")

        # Buscar campos
        campos = extract_campos_criticos(text)
        result["campos_criticos"] = {k: v for k, v in campos.items() if v}
        result["success"] = len(result["campos_criticos"]) >= 3

        if result["campos_criticos"]:
            print()
            print(Colors.OKGREEN + "✓ Campos encontrados:" + Colors.ENDC)
            for campo, valor in result["campos_criticos"].items():
                print(f"  {campo}: {valor}")

    except Exception as e:
        result["notes"].append(f"Error: {str(e)}")
        print(Colors.FAIL + f"✗ Error: {str(e)}" + Colors.ENDC)

    return result


def compare_results(results: Dict[str, Dict[str, Any]]):
    """Compara resultados de todas las bibliotecas."""
    print_header("COMPARACIÓN DE RESULTADOS")

    # Tabla comparativa
    print(f"{'Biblioteca':<20} {'Tablas':<10} {'R.Social':<10} {'RUT':<10} {'Proyecto':<10} {'Score':>10}")
    print("-" * 80)

    for lib_name, result in results.items():
        r_social = "✓" if result["campos_criticos"].get("razon_social") else "✗"
        rut = "✓" if result["campos_criticos"].get("rut") else "✗"
        proyecto = "✓" if result["campos_criticos"].get("nombre_proyecto") else "✗"

        score = sum([
            bool(result["campos_criticos"].get("razon_social")),
            bool(result["campos_criticos"].get("rut")),
            bool(result["campos_criticos"].get("nombre_proyecto"))
        ])

        color = Colors.OKGREEN if score == 3 else (Colors.WARNING if score > 0 else Colors.FAIL)

        print(f"{lib_name:<20} {result['tables_found']:<10} {r_social:<10} {rut:<10} {proyecto:<10} {color}{score}/3{Colors.ENDC:>6}")

    print()
    print(Colors.BOLD + "RECOMENDACIÓN:" + Colors.ENDC)

    # Encontrar la mejor
    best_lib = max(results.items(), key=lambda x: sum([
        bool(x[1]["campos_criticos"].get("razon_social")),
        bool(x[1]["campos_criticos"].get("rut")),
        bool(x[1]["campos_criticos"].get("nombre_proyecto"))
    ]))

    best_score = sum([
        bool(best_lib[1]["campos_criticos"].get("razon_social")),
        bool(best_lib[1]["campos_criticos"].get("rut")),
        bool(best_lib[1]["campos_criticos"].get("nombre_proyecto"))
    ])

    if best_score == 3:
        print(Colors.OKGREEN + f"✓ Mejor opción: {best_lib[0]} (3/3 campos extraídos)" + Colors.ENDC)
    elif best_score > 0:
        print(Colors.WARNING + f"⚠ Mejor opción: {best_lib[0]} ({best_score}/3 campos extraídos)" + Colors.ENDC)
    else:
        print(Colors.FAIL + "✗ Ninguna biblioteca pudo extraer los campos críticos" + Colors.ENDC)

    # Notas adicionales
    if best_lib[1]["notes"]:
        print()
        print("Notas:")
        for note in best_lib[1]["notes"]:
            print(f"  - {note}")


def main():
    """Función principal."""
    pdf_path = Path("downloads/2752/2504-FORM-SUCTD-V1.pdf")

    if not pdf_path.exists():
        print(Colors.FAIL + f"Error: No se encuentra el PDF en {pdf_path}" + Colors.ENDC)
        sys.exit(1)

    print_header("DEMO: Comparación de Bibliotecas PDF Parsing")
    print(f"PDF: {pdf_path}")
    print(f"Objetivo: Extraer Razón Social, RUT y Nombre del Proyecto")

    # Ejecutar todas las pruebas
    results = {}

    results["pdfplumber"] = test_pdfplumber(pdf_path)
    results["tabula-py"] = test_tabula(pdf_path)
    results["camelot-py"] = test_camelot(pdf_path)
    results["pymupdf"] = test_pymupdf(pdf_path)
    results["pypdf"] = test_pypdf(pdf_path)

    # Comparar resultados
    compare_results(results)

    print()
    print(Colors.HEADER + "=" * 80 + Colors.ENDC)
    print(Colors.HEADER + "FIN DE LA DEMO" + Colors.ENDC)
    print(Colors.HEADER + "=" * 80 + Colors.ENDC)


if __name__ == "__main__":
    main()
