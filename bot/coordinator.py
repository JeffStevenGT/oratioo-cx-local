"""
coordinator.py — Orquestador multi-worker con PostgreSQL local
===============================================================
Gestiona workers en paralelo, asigna proxies exclusivos.
Comunicación con PostgreSQL vía pg_client.

USO:
  python coordinator.py --workers 4
  python coordinator.py --machine-name localhost --workers 5
"""

import os
import sys
import time
import random
import subprocess
import threading
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Buscar .env
_env_path = find_dotenv(usecwd=True)
if not _env_path:
    _env_path = str(Path(__file__).parent.parent / ".env")
load_dotenv(_env_path)

from pg_client import contar_estados, limpiar_duplicados_lineas

# ── Config ────────────────────────────────────────

WORKER_SCRIPT = Path(__file__).parent / "worker.py"
PROXIES_FILE = Path(__file__).parent / "proxies.txt"

MAQUINA_NOMBRE = os.getenv("MAQUINA_NOMBRE", f"PC-local")
HEARTBEAT_INTERVAL = 30

# ── Estado global ─────────────────────────────────

workers_activos = {}
detener = False
lock = threading.Lock()


# ── Proxies ───────────────────────────────────────

def _parsear_proxy(linea: str) -> dict | None:
    """Parsea una línea de proxies.txt. Formato: ip:puerto:usuario:contraseña"""
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None
    partes = linea.split(":")
    if len(partes) == 4:
        return {
            "ip": partes[0],
            "puerto": partes[1],
            "usuario": partes[2],
            "password": partes[3],
            "server": f"http://{partes[0]}:{partes[1]}",
        }
    return None


def cargar_todos_los_proxies() -> list[dict]:
    """Carga todos los proxies desde proxies.txt."""
    proxies = []
    if not PROXIES_FILE.exists():
        print(f"[Coordinator] No existe {PROXIES_FILE}")
        return proxies
    with open(PROXIES_FILE, "r", encoding="utf-8") as f:
        for linea in f:
            p = _parsear_proxy(linea)
            if p:
                proxies.append(p)
    print(f"[Coordinator] 📡 {len(proxies)} proxies cargados")
    return proxies


# ── Workers ───────────────────────────────────────

def lanzar_worker(worker_id: int, proxy: dict | None) -> subprocess.Popen | None:
    """Lanza un worker.py como proceso independiente."""
    env = os.environ.copy()
    if proxy:
        env["PROXY_SERVER"] = proxy["server"]
        env["PROXY_USER"] = proxy.get("usuario", "")
        env["PROXY_PASS"] = proxy.get("password", "")
    env["WORKER_ID"] = str(worker_id)
    env["WORKER_MAQUINA"] = MAQUINA_NOMBRE

    try:
        proc = subprocess.Popen([sys.executable, str(WORKER_SCRIPT)], env=env)
        print(f"[Coordinator] ▶ Worker #{worker_id} iniciado "
              f"{'(proxy: '+proxy['ip']+')' if proxy else '(sin proxy)'}")
        return proc
    except Exception as e:
        print(f"[Coordinator] ❌ Error lanzando worker #{worker_id}: {e}")
        return None


def detener_todos_los_workers():
    """Detiene todos los workers activos."""
    with lock:
        for wid, winfo in list(workers_activos.items()):
            try:
                winfo["process"].terminate()
            except Exception:
                pass
        workers_activos.clear()


# ── Monitoreo ─────────────────────────────────────

def monitor_workers_loop():
    """Hilo que monitorea y revive workers caídos."""
    global detener
    while not detener:
        time.sleep(10)
        with lock:
            for wid, winfo in list(workers_activos.items()):
                proc = winfo["process"]
                if proc.poll() is not None:
                    print(f"[Coordinator] ⚠ Worker #{wid} terminó (exit={proc.returncode}). Reviviendo...")
                    proxy = winfo.get("proxy")
                    new_proc = lanzar_worker(wid, proxy)
                    if new_proc:
                        workers_activos[wid] = {"process": new_proc, "proxy": proxy,
                                                "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                            time.gmtime())}


def status_loop():
    """Hilo que muestra estado cada 3 horas."""
    global detener
    while not detener:
        time.sleep(10800)  # 3 horas
        if detener:
            break
        try:
            estados = contar_estados()
            t = time.strftime("%H:%M:%S")
            print(f"[{t}] 📊 STATUS: {estados['completado']} completados | "
                  f"{estados['pendiente']} pendientes | {estados['error']} errores | "
                  f"Workers: {len(workers_activos)}")
        except Exception as ex:
            print(f"[STATUS] Error: {ex}")


# ── Main ──────────────────────────────────────────

def main():
    global detener
    import argparse

    parser = argparse.ArgumentParser(description="Oratioo CX Coordinator — PostgreSQL local")
    parser.add_argument("--workers", type=int, default=4, help="Número de workers (default: 4)")
    parser.add_argument("--machine-name", type=str, default=None, help="Nombre de la máquina")
    args = parser.parse_args()

    global MAQUINA_NOMBRE
    if args.machine_name:
        MAQUINA_NOMBRE = args.machine_name
        os.environ["MAQUINA_NOMBRE"] = MAQUINA_NOMBRE

    num_workers = max(1, args.workers)
    print(f"[Coordinator] 🚀 Iniciando con {num_workers} workers en '{MAQUINA_NOMBRE}'...")

    # ── Limpiar duplicados ──
    limpiar_duplicados_lineas()

    # ── Cargar proxies ──
    todos_proxies = cargar_todos_los_proxies()

    # ── Mostrar cola inicial ──
    estados = contar_estados()
    print(f"[Coordinator] 📊 Cola: {estados['pendiente']} pendientes, "
          f"{estados['completado']} completados, {estados['error']} errores")

    # ── Lanzar workers (con stagger) ──
    for i in range(num_workers):
        proxy = todos_proxies[i % len(todos_proxies)] if todos_proxies else None
        proc = lanzar_worker(i + 1, proxy)
        if proc:
            with lock:
                workers_activos[i + 1] = {
                    "process": proc,
                    "proxy": proxy,
                    "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                }
        time.sleep(2)  # Stagger

    # ── Hilos de monitoreo ──
    monitor_thread = threading.Thread(target=monitor_workers_loop, daemon=True)
    monitor_thread.start()

    status_thread = threading.Thread(target=status_loop, daemon=True)
    status_thread.start()

    # ── Esperar Ctrl+C ──
    print("[Coordinator] Presiona Ctrl+C para detener.")
    try:
        while not detener:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Coordinator] ⏹ Deteniendo...")
        detener = True
        detener_todos_los_workers()
        print("[Coordinator] 👋 Bye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
