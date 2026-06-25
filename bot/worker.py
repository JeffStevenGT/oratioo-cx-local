"""
worker.py — Worker individual con PostgreSQL local
===================================================
Lanzado por coordinator.py. Cada worker:
  - Usa su propio proxy (asignado exclusivamente)
  - Toma DNIs de la cola en PostgreSQL (estado = pendiente)
  - Los procesa uno por uno
  - Guarda resultados directo a PostgreSQL

USO (normalmente lanzado por coordinator.py):
  PROXY_SERVER=http://... PROXY_USER=u PROXY_PASS=p WORKER_ID=1 python worker.py
"""

import os
import sys
import time
import random
import json
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Buscar .env
_env_path = find_dotenv(usecwd=True)
if not _env_path:
    _env_path = str(Path(__file__).parent.parent / ".env")
load_dotenv(_env_path)

from playwright.sync_api import sync_playwright

from login import (
    manejar_cookies_flexible,
    realizar_login,
    seleccionar_marca_orange,
    abrir_nuevo_acto_comercial,
    verificar_sesion_valida,
    LoginError,
    MaxSessionsError,
    PangeaDownError,
)
from browser_setup import crear_contexto_espana
from pg_client import (
    tomar_siguiente_dni,
    guardar_resultado,
    actualizar_progreso_documento,
)

load_dotenv()

# ── Config ────────────────────────────────────────

WORKER_ID = int(os.getenv("WORKER_ID", "0"))
MAQUINA = os.getenv("WORKER_MAQUINA", "local")
ORANGE_URL = "https://pangea.orange.es/"
MAX_DNIS = int(os.getenv("MAX_DNIS_POR_WORKER", "0"))
BOT_API_URL = os.getenv("BOT_API_URL", "http://localhost:3001")
BOT_API_KEY = os.getenv("BOT_API_KEY", "oratioo-bot-internal-key")

# Proxy desde env (asignado por coordinator)
PROXY_CONFIG = None
if os.getenv("PROXY_SERVER"):
    PROXY_CONFIG = {
        "server": os.getenv("PROXY_SERVER"),
        "username": os.getenv("PROXY_USER", ""),
        "password": os.getenv("PROXY_PASS", ""),
    }


def log(msg: str):
    t = time.strftime("%H:%M:%S")
    try:
        print(f"[W{WORKER_ID}|{t}] {msg}", flush=True)
    except UnicodeEncodeError:
        print(f"[W{WORKER_ID}|{t}] {msg.encode('ascii', 'replace').decode()}", flush=True)


# ══════════════════════════════════════════════════════════════
#  PROCESAR UN DNI
# ══════════════════════════════════════════════════════════════

def procesar_dni(page, dni: str, linea_id: int = None, modal_ya_abierto: bool = False) -> tuple:
    """Procesa un solo DNI.
    Retorna (exito: bool, modal_sigue_abierto: bool).
    """
    try:
        from extraction import extraer_datos_cliente
        filas = extraer_datos_cliente(page, dni, buscar_por_dni=True,
                                      modal_ya_abierto=modal_ya_abierto)

        if not filas:
            log(f"[WARN] {dni}: sin resultados")
            return False, False

        # Procesar resultados
        for fila in filas:
            es_cima = fila.get("es_cima", False)
            nombre = fila.get("Nombre", "")
            no_cliente = nombre == "NO ES CLIENTE"
            es_bloqueado = nombre in ("CLIENTE PYME", "CLIENTE GGCC", "CLIENTE MAX LINEAS", "YA_PROCESADO")
            es_error = nombre in ("ERROR CAMPANAS",)
            modal_abierto = fila.get("_modal_abierto", False)

            if fila.get("_skip"):
                continue

            if no_cliente or es_bloqueado:
                estado_final = "no_cliente"
                datos = {
                    "nombre": nombre,
                    "linea_principal": dni,
                    "paquete": "N/A",
                    "worker_id": WORKER_ID,
                    "maquina": MAQUINA,
                    "atributos_dinamicos": {
                        "estado": estado_final,
                        "datos_basicos": {"dni": dni},
                        "cima": "NO",
                        "renove_mixto_variante": "N/A",
                        "linea": {"numero": dni, "es_cima": False, "tiene_renove_mixto": False},
                    },
                }
                guardar_resultado(dni, datos, estado=estado_final, linea_id=linea_id)
            elif es_error:
                estado_final = "error"
                datos = {
                    "nombre": "ERROR CAMPANAS",
                    "linea_principal": dni,
                    "paquete": "N/A",
                    "worker_id": WORKER_ID,
                    "maquina": MAQUINA,
                    "atributos_dinamicos": {"estado": "error"},
                }
                guardar_resultado(dni, datos, estado="error", linea_id=linea_id)
            else:
                # Empaquetar atributos dinámicos
                dinamicos = {
                    "cima": "SI" if es_cima else "NO",
                    "tiene_renove_mixto": fila.get("tiene_renove_mixto", False),
                    "renove_mixto_variante": fila.get("variante_renove", "N/A"),
                    "renove_mixto_todas": fila.get("variante_renove", "N/A"),
                    "tipo_renove": fila.get("variante_renove", "N/A"),
                    "estado": "completado",
                    "cima_tags": fila.get("tiene_tv", False) and "TV" or "N/A",
                    "etiquetas": fila.get("etiquetas", []),
                    "es_principal": fila.get("es_principal", False),
                    "activo_desde": fila.get("activo_desde", "N/A"),
                    "producto": fila.get("producto", "N/A"),
                    "estado_linea": fila.get("estado_linea", []),
                    "permanencia": fila.get("permanencia", "N/A"),
                    "permanencia_fecha": fila.get("permanencia_fecha", ""),
                    "consumo": fila.get("consumo", "N/A"),
                    "venta_plazos": fila.get("venta_plazos", "N/A"),
                    "campanas_extra": fila.get("campanas_extra", []),
                    "notificacion_pack": fila.get("notificacion_pack", ""),
                    "datos_basicos": {
                        "nombre": fila.get("Nombre", "N/A"),
                        "direccion": fila.get("Direccion", "N/A"),
                        "seg_fijo": fila.get("Seg Fijo", "N/A"),
                        "seg_movil": fila.get("Seg Movil", "N/A"),
                        "dni": dni,
                    },
                }

                datos = {
                    "nombre": fila.get("Nombre", "N/A"),
                    "direccion": fila.get("Direccion", "N/A"),
                    "linea_principal": fila.get("Linea", "N/A"),
                    "seg_fijo": fila.get("Seg Fijo", "N/A"),
                    "seg_movil": fila.get("Seg Movil", "N/A"),
                    "paquete": fila.get("Paquete", "N/A"),
                    "worker_id": WORKER_ID,
                    "maquina": MAQUINA,
                    "atributos_dinamicos": dinamicos,
                }

                guardar_resultado(dni, datos, estado="completado", linea_id=linea_id)

        return True, modal_abierto if filas else False

    except Exception as e:
        log(f"[ERR] {dni}: {e}")
        try:
            datos = {
                "nombre": "ERROR",
                "linea_principal": dni,
                "worker_id": WORKER_ID,
                "maquina": MAQUINA,
                "atributos_dinamicos": {"estado": "error", "error_msg": str(e)[:200]},
            }
            guardar_resultado(dni, datos, estado="error", linea_id=linea_id)
        except Exception:
            pass
        return False, False


# ══════════════════════════════════════════════════════════════
#  MAIN
# ══════════════════════════════════════════════════════════════

def main():
    global detener
    detener = False
    procesados = 0
    errores = 0
    errores_consecutivos = 0

    log(f"🚀 Worker iniciado [maquina={MAQUINA}]")

    # ── Iniciar navegador ──
    with sync_playwright() as pw:
        browser, context = crear_contexto_espana(pw, proxy_config=PROXY_CONFIG)
        page = context.new_page()

        try:
            # ── Login inicial ──
            page.goto(ORANGE_URL, timeout=90000)
            manejar_cookies_flexible(page)
            realizar_login(page)
            seleccionar_marca_orange(page)
            abrir_nuevo_acto_comercial(page)
            modal_abierto = False
            log("[OK] Login inicial exitoso")

            while not detener:
                # ── Tomar siguiente DNI de la cola ──
                fila = tomar_siguiente_dni(worker_id=WORKER_ID, maquina=MAQUINA)
                if fila is None:
                    log("[IDLE] Sin DNIs pendientes. Esperando 10s...")
                    time.sleep(10)
                    continue

                dni = fila["dni"]
                linea_id = fila["id"]
                log(f"📋 Procesando: {dni}")

                # ── Procesar ──
                exito, modal_abierto = procesar_dni(page, dni, linea_id=linea_id,
                                                    modal_ya_abierto=modal_abierto)

                if exito:
                    procesados += 1
                    errores_consecutivos = 0
                else:
                    errores += 1
                    errores_consecutivos += 1

                # ── Pausa entre DNIs ──
                time.sleep(random.uniform(1.5, 3.0))

                # ── Verificar sesión cada 5 DNIs ──
                if (procesados + errores) % 5 == 0:
                    try:
                        if not verificar_sesion_valida(page):
                            log("[RETRY] Sesión expirada, relogueando...")
                            page.goto(ORANGE_URL, timeout=30000)
                            realizar_login(page)
                            seleccionar_marca_orange(page)
                            abrir_nuevo_acto_comercial(page)
                            modal_abierto = False
                    except Exception:
                        pass

                # ── Verificar límite ──
                if MAX_DNIS > 0 and (procesados + errores) >= MAX_DNIS:
                    log(f"🏁 Límite alcanzado ({MAX_DNIS} DNIs). Reseteando contador.")
                    procesados = 0
                    errores = 0

        except KeyboardInterrupt:
            log("⏹ Detenido por señal")
            detener = True
        except Exception as e:
            log(f"[CRIT] Error crítico: {e}")
            import traceback
            traceback.print_exc()
        finally:
            log("[CLEANUP] Cerrando navegador...")
            try:
                page.close()
            except Exception:
                pass
            try:
                context.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            log("[CLEANUP] Navegador cerrado")

    log(f"🏁 Worker finalizado → [OK] {procesados} | [ERR] {errores}")


if __name__ == "__main__":
    main()
