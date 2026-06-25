"""
pg_client.py — Comunicación directa con PostgreSQL vía psycopg2
=================================================================
Reemplaza supabase_client.py. Usa psycopg2 para queries directas.
El estado del DNI se guarda dentro de atributos_dinamicos (JSONB).

Estados de un DNI (dentro de atributos_dinamicos):
  pendiente     → espera ser procesado
  en_progreso   → un worker lo está procesando ahora
  completado    → procesado exitosamente
  error         → falló después de reintentos
  no_cliente    → DNI no encontrado en Orange
"""

import os
import json
import time
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5433/oratioo_cx")


def get_conn():
    """Obtiene una conexión a PostgreSQL."""
    return psycopg2.connect(DATABASE_URL)


# ══════════════════════════════════════════════════════════════
#  GUARDAR RESULTADO
# ══════════════════════════════════════════════════════════════

def guardar_resultado(dni: str, datos: dict, estado: str = "completado", linea_id: int = None,
                      force_create: bool = False):
    """
    Guarda/actualiza los datos de un DNI en PostgreSQL (UPSERT).

    Si linea_id se pasa, actualiza esa fila específica.
    Si force_create=True, SIEMPRE crea un nuevo registro.
    Si no, busca por DNI (comportamiento legacy).

    Estados:
      - completado  → procesado exitosamente
      - no_cliente  → DNI no encontrado en Orange
      - error       → fallo técnico
    """
    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        if force_create:
            existente = None
        elif linea_id:
            cur.execute("SELECT id, atributos_dinamicos FROM lineas WHERE id = %s LIMIT 1", (linea_id,))
            existente = cur.fetchone()
        else:
            cur.execute(
                "SELECT id, atributos_dinamicos FROM lineas WHERE dni = %s ORDER BY id DESC LIMIT 1",
                (dni,)
            )
            existente = cur.fetchone()

        # ── Merge de atributos_dinamicos previos ──
        ad_prev = {}
        if existente:
            prev_ad = existente.get("atributos_dinamicos", {}) or {}
            if isinstance(prev_ad, str):
                try:
                    prev_ad = json.loads(prev_ad)
                except Exception:
                    prev_ad = {}
            # Preservar pipeline, documento_id, datos_basicos, etc.
            for k, v in prev_ad.items():
                if k not in ("estado", "fecha_procesado", "fecha_hora", "worker_id", "maquina"):
                    ad_prev[k] = v

        ad_nuevo = datos.get("atributos_dinamicos", {})
        for k, v in ad_nuevo.items():
            # Preservar renove_mixto_variante si ya existe uno mejor
            if k == "renove_mixto_variante" and k in ad_prev:
                if v not in (None, "N/A", ""):
                    ad_prev[k] = v
            elif k == "tiene_renove_mixto" and k in ad_prev:
                if v:
                    ad_prev[k] = True
            else:
                ad_prev[k] = v

        ad_prev["estado"] = estado
        ad_prev["fecha_procesado"] = time.strftime("%Y-%m-%d")
        ad_prev["fecha_hora"] = ahora
        ad_prev["worker_id"] = datos.get("worker_id", 0)
        ad_prev["maquina"] = datos.get("maquina", "local")

        if existente:
            cur.execute(
                """UPDATE lineas
                   SET nombre = %(nombre)s,
                       direccion = %(direccion)s,
                       linea = %(linea)s,
                       seg_fijo = %(seg_fijo)s,
                       seg_movil = %(seg_movil)s,
                       paquete = %(paquete)s,
                       atributos_dinamicos = %(ad)s::jsonb
                   WHERE id = %(id)s""",
                {
                    "nombre": datos.get("nombre", "N/A"),
                    "direccion": datos.get("direccion", "N/A"),
                    "linea": datos.get("linea_principal", "N/A"),
                    "seg_fijo": datos.get("seg_fijo", "N/A"),
                    "seg_movil": datos.get("seg_movil", "N/A"),
                    "paquete": datos.get("paquete", "N/A"),
                    "ad": json.dumps(ad_prev),
                    "id": existente["id"],
                },
            )
        else:
            cur.execute(
                """INSERT INTO lineas (dni, nombre, direccion, linea, seg_fijo, seg_movil, paquete, atributos_dinamicos)
                   VALUES (%(dni)s, %(nombre)s, %(direccion)s, %(linea)s, %(seg_fijo)s, %(seg_movil)s, %(paquete)s, %(ad)s::jsonb)""",
                {
                    "dni": dni,
                    "nombre": datos.get("nombre", "N/A"),
                    "direccion": datos.get("direccion", "N/A"),
                    "linea": datos.get("linea_principal", "N/A"),
                    "seg_fijo": datos.get("seg_fijo", "N/A"),
                    "seg_movil": datos.get("seg_movil", "N/A"),
                    "paquete": datos.get("paquete", "N/A"),
                    "ad": json.dumps(ad_prev),
                },
            )

        conn.commit()
        icono = "✅" if estado == "completado" else "❌" if estado == "no_cliente" else "⚠"
        accion = "actualizado" if existente else "insertado"
        print(f"  [PostgreSQL] {icono} {dni} {accion} ({estado})")

    except Exception as e:
        print(f"  [PostgreSQL] Error guardando {dni}: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  INSERTAR DNIs (encolar)
# ══════════════════════════════════════════════════════════════

def insertar_dnis(dnis: list[str], semana: str = "", documento_id: int = None) -> int:
    """Inserta una lista de DNIs con estado 'pendiente'."""
    if not dnis:
        return 0

    ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    conn = get_conn()
    cur = conn.cursor()
    try:
        rows = [
            (d.strip(), d.strip(),
             json.dumps({
                 "estado": "pendiente",
                 "semana": semana,
                 "fecha_encolado": time.strftime("%Y-%m-%d"),
                 "documento_id": str(documento_id) if documento_id else None,
             }))
            for d in dnis if d.strip()
        ]
        psycopg2.extras.execute_values(
            cur,
            "INSERT INTO lineas (dni, linea, atributos_dinamicos) VALUES %s",
            rows,
            template="(%s, %s, %s::jsonb)",
        )
        conn.commit()
        return len(rows)
    except Exception as e:
        print(f"  [PostgreSQL] Error insertando DNIs: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  CONTAR ESTADOS
# ══════════════════════════════════════════════════════════════

def contar_estados(semana: str = "") -> dict:
    """Retorna conteo de DNIs por estado."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT atributos_dinamicos->>'estado' AS estado, COUNT(*) AS cnt
               FROM lineas
               GROUP BY atributos_dinamicos->>'estado'"""
        )
        conteo = {"pendiente": 0, "en_progreso": 0, "completado": 0, "error": 0, "no_cliente": 0}
        for row in cur.fetchall():
            est = row[0] or "pendiente"
            if est in conteo:
                conteo[est] = row[1]
        return conteo
    except Exception as e:
        print(f"  [PostgreSQL] Error contando estados: {e}")
        return {"pendiente": 0, "en_progreso": 0, "completado": 0, "error": 0}
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  TOMAR SIGUIENTE DNI (cola)
# ══════════════════════════════════════════════════════════════

def tomar_siguiente_dni(worker_id: int = 0, maquina: str = "local") -> dict | None:
    """Toma el próximo DNI pendiente de la cola con SELECT FOR UPDATE para evitar race conditions."""
    conn = get_conn()
    cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        # Bloquear fila con FOR UPDATE SKIP LOCKED para concurrencia
        cur.execute(
            """SELECT id, dni, atributos_dinamicos
               FROM lineas
               WHERE atributos_dinamicos->>'estado' = 'pendiente'
               ORDER BY created_at ASC
               LIMIT 1
               FOR UPDATE SKIP LOCKED"""
        )
        fila = cur.fetchone()
        if not fila:
            return None

        # Merge atributos existentes
        ad = fila.get("atributos_dinamicos", {})
        if isinstance(ad, str):
            try:
                ad = json.loads(ad)
            except Exception:
                ad = {}

        ad["estado"] = "en_progreso"
        ad["worker_id"] = worker_id
        ad["maquina"] = maquina

        cur.execute(
            "UPDATE lineas SET atributos_dinamicos = %s::jsonb WHERE id = %s",
            (json.dumps(ad), fila["id"]),
        )
        conn.commit()

        return {"id": fila["id"], "dni": fila["dni"]}
    except Exception as e:
        print(f"  [PostgreSQL] Error tomando DNI: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  VERIFICAR SI UN CLIENTE YA EXISTE
# ══════════════════════════════════════════════════════════════

def cliente_ya_procesado(dni: str) -> bool:
    """Verifica si un DNI ya fue procesado (completado)."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT 1 FROM lineas
               WHERE dni = %s
                 AND atributos_dinamicos->>'estado' = 'completado'
               LIMIT 1""",
            (dni,),
        )
        return cur.fetchone() is not None
    except Exception:
        return False
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  DOCUMENTOS
# ══════════════════════════════════════════════════════════════

def crear_documento(nombre_archivo: str, total_dnis: int, dnis: list[str] = None) -> int | None:
    """Crea un registro de documento y retorna su ID."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO documentos (nombre_archivo, total_dnis, estado, procesados)
               VALUES (%s, %s, 'analizando', 0) RETURNING id""",
            (nombre_archivo, total_dnis),
        )
        doc_id = cur.fetchone()[0]
        conn.commit()
        return doc_id
    except Exception as e:
        print(f"  [PostgreSQL] Error creando documento: {e}")
        conn.rollback()
        return None
    finally:
        cur.close()
        conn.close()


def actualizar_progreso_documento(doc_id: int, incremento: int = 1):
    """Incrementa el contador de procesados de un documento."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE documentos SET procesados = procesados + %s WHERE id = %s",
            (incremento, doc_id),
        )
        # Verificar si se completó
        cur.execute("SELECT total_dnis, procesados FROM documentos WHERE id = %s", (doc_id,))
        row = cur.fetchone()
        if row and row[1] >= row[0]:
            cur.execute("UPDATE documentos SET estado = 'completado' WHERE id = %s", (doc_id,))
        conn.commit()
    except Exception as e:
        print(f"  [PostgreSQL] Error actualizando progreso: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  RESETEAR COLA (poner en_progreso/error de vuelta a pendiente)
# ══════════════════════════════════════════════════════════════

def resetear_cola():
    """Pone todos los DNIs no completados de vuelta a pendiente."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """UPDATE lineas
               SET atributos_dinamicos = jsonb_set(
                   jsonb_set(atributos_dinamicos, '{estado}', '"pendiente"'),
                   '{worker_id}', 'null'
               )
               WHERE atributos_dinamicos->>'estado' IN ('en_progreso', 'error')"""
        )
        afectados = cur.rowcount
        conn.commit()
        print(f"  [PostgreSQL] Cola reseteada: {afectados} DNIs vueltos a pendiente")
        return afectados
    except Exception as e:
        print(f"  [PostgreSQL] Error reseteando cola: {e}")
        conn.rollback()
        return 0
    finally:
        cur.close()
        conn.close()


# ══════════════════════════════════════════════════════════════
#  LIMPIAR DUPLICADOS
# ══════════════════════════════════════════════════════════════

def limpiar_duplicados_lineas():
    """Elimina líneas duplicadas (mismo dni + misma linea) conservando la más reciente."""
    conn = get_conn()
    cur = conn.cursor()
    try:
        cur.execute(
            """DELETE FROM lineas
               WHERE id NOT IN (
                   SELECT MIN(id) FROM lineas
                   GROUP BY dni, linea
               )
               AND atributos_dinamicos->>'estado' IN ('pendiente', 'error')"""
        )
        eliminados = cur.rowcount
        conn.commit()
        if eliminados > 0:
            print(f"  [PostgreSQL] {eliminados} duplicados eliminados")
    except Exception as e:
        print(f"  [PostgreSQL] Error limpiando duplicados: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()
