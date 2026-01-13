"""
Backfill proyectos_history desde raw_data.

Recrea el historial de cambios comparando snapshots históricos de la API.
"""

import json
import os
from datetime import datetime
from decimal import Decimal
from dotenv import load_dotenv
import mysql.connector

# Cargar .env desde la raíz del proyecto
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

COMPARE_FIELDS = [
    "expediente_nombre", "workflow_descripcion", "region_nombre", "comuna_nombre",
    "tipo_proyecto", "descripcion_tipologia", "razon_ingreso", "titular",
    "inversion_mm", "estado_proyecto", "encargado", "actividad_actual", "etapa",
    "fecha_plazo", "dias_legales", "suspendido"
]

HISTORY_SNAPSHOT_FIELDS = [
    "expediente_nombre", "workflow_descripcion", "region_nombre", "tipo_proyecto",
    "titular", "estado_proyecto", "actividad_actual", "etapa", "inversion_mm"
]


def get_connection():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 3306)),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        database=os.getenv("DB_NAME"),
    )


def normalize_value(val):
    """Normaliza valores para comparación."""
    if val is None:
        return None
    if isinstance(val, Decimal):
        return float(val)
    if isinstance(val, str):
        return val.strip() if val.strip() else None
    return val


def parse_raw_data_row(row: dict) -> list[dict]:
    """Parsea una fila de raw_data y retorna lista de proyectos."""
    try:
        data = json.loads(row["data"])
        if isinstance(data, dict) and "data" in data:
            proyectos = data["data"]
        elif isinstance(data, list):
            proyectos = data
        else:
            return []

        # Normalizar keys a minúsculas
        result = []
        for p in proyectos:
            normalized = {}
            for k, v in p.items():
                key = k.lower()
                # Mapear algunos campos
                if key == "inversion_mm":
                    try:
                        normalized[key] = float(v) if v else None
                    except (ValueError, TypeError):
                        normalized[key] = None
                else:
                    normalized[key] = v
            result.append(normalized)
        return result
    except (json.JSONDecodeError, KeyError, TypeError):
        return []


def detect_changes(old: dict, new: dict) -> list[dict]:
    """Detecta cambios entre dos versiones de un proyecto."""
    changes = []
    for field in COMPARE_FIELDS:
        old_val = normalize_value(old.get(field))
        new_val = normalize_value(new.get(field))
        if old_val != new_val:
            changes.append({
                "field": field,
                "old": old_val,
                "new": new_val
            })
    return changes


def get_snapshots_by_date(conn) -> dict[str, dict[int, dict]]:
    """
    Obtiene todos los snapshots agrupados por fecha.
    Retorna: {fecha_str: {expediente_id: proyecto_dict}}
    """
    cursor = conn.cursor(dictionary=True)
    cursor.execute("""
        SELECT DATE(extracted_at) as fecha, data
        FROM raw_data
        WHERE status_code = 200 AND data IS NOT NULL
        ORDER BY extracted_at
    """)

    snapshots = {}
    for row in cursor:
        fecha = str(row["fecha"])
        if fecha not in snapshots:
            snapshots[fecha] = {}

        proyectos = parse_raw_data_row(row)
        for p in proyectos:
            exp_id = p.get("expediente_id")
            if exp_id:
                try:
                    exp_id = int(exp_id)
                    snapshots[fecha][exp_id] = p
                except (ValueError, TypeError):
                    pass

    cursor.close()
    return snapshots


def truncate_str(val, max_len):
    """Trunca string a max_len si es necesario."""
    if val is None:
        return None
    s = str(val)
    return s[:max_len] if len(s) > max_len else s


def insert_history_batch(conn, records: list[dict]):
    """Inserta batch de registros en proyectos_history."""
    if not records:
        return

    cursor = conn.cursor()
    sql = """
        INSERT INTO proyectos_history (
            expediente_id, operation, changed_at, pipeline_run_id, changed_fields,
            expediente_nombre, workflow_descripcion, region_nombre, tipo_proyecto,
            titular, estado_proyecto, actividad_actual, etapa, inversion_mm
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
        )
    """

    for r in records:
        values = (
            r["expediente_id"],
            r["operation"],
            r["changed_at"],
            None,  # pipeline_run_id (backfill, no tiene run asociado)
            json.dumps(r["changed_fields"]) if r["changed_fields"] else None,
            truncate_str(r.get("expediente_nombre"), 500),
            truncate_str(r.get("workflow_descripcion"), 50),
            truncate_str(r.get("region_nombre"), 100),
            truncate_str(r.get("tipo_proyecto"), 50),
            truncate_str(r.get("titular"), 255),
            truncate_str(r.get("estado_proyecto"), 100),
            truncate_str(r.get("actividad_actual"), 255),
            truncate_str(r.get("etapa"), 100),
            r.get("inversion_mm"),
        )
        cursor.execute(sql, values)

    conn.commit()
    cursor.close()


def clear_backfill_history(conn):
    """Limpia solo registros de backfill (pipeline_run_id IS NULL)."""
    cursor = conn.cursor()
    cursor.execute("DELETE FROM proyectos_history WHERE pipeline_run_id IS NULL")
    deleted = cursor.rowcount
    conn.commit()
    cursor.close()
    print(f"Backfill anterior limpiado ({deleted} registros)")


def backfill():
    """Ejecuta el backfill completo."""
    conn = get_connection()

    print("Cargando snapshots desde raw_data...")
    snapshots = get_snapshots_by_date(conn)

    fechas = sorted(snapshots.keys())
    print(f"Encontradas {len(fechas)} fechas de snapshot: {fechas}")

    if not fechas:
        print("No hay snapshots para procesar")
        return

    # Limpiar backfill anterior (mantener registros del pipeline)
    clear_backfill_history(conn)

    stats = {"inserts": 0, "updates": 0, "sin_cambios": 0}
    previous_snapshot = {}

    for fecha in fechas:
        current_snapshot = snapshots[fecha]
        changed_at = datetime.strptime(fecha, "%Y-%m-%d")

        records_to_insert = []

        for exp_id, proyecto in current_snapshot.items():
            if exp_id not in previous_snapshot:
                # Nuevo proyecto (INSERT)
                records_to_insert.append({
                    "expediente_id": exp_id,
                    "operation": "INSERT",
                    "changed_at": changed_at,
                    "changed_fields": None,
                    **{f: proyecto.get(f) for f in HISTORY_SNAPSHOT_FIELDS}
                })
                stats["inserts"] += 1
            else:
                # Proyecto existente - verificar cambios
                changes = detect_changes(previous_snapshot[exp_id], proyecto)
                if changes:
                    records_to_insert.append({
                        "expediente_id": exp_id,
                        "operation": "UPDATE",
                        "changed_at": changed_at,
                        "changed_fields": changes,
                        **{f: proyecto.get(f) for f in HISTORY_SNAPSHOT_FIELDS}
                    })
                    stats["updates"] += 1
                else:
                    stats["sin_cambios"] += 1

        if records_to_insert:
            insert_history_batch(conn, records_to_insert)
            print(f"  {fecha}: {len(records_to_insert)} registros insertados")
        else:
            print(f"  {fecha}: sin cambios detectados")

        # Actualizar snapshot anterior (merge, no reemplazar)
        previous_snapshot.update(current_snapshot)

    conn.close()

    print("\n=== Backfill completado ===")
    print(f"  INSERTs: {stats['inserts']}")
    print(f"  UPDATEs: {stats['updates']}")
    print(f"  Sin cambios: {stats['sin_cambios']}")
    print(f"  Total en history: {stats['inserts'] + stats['updates']}")


if __name__ == "__main__":
    backfill()
