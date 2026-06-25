"""
browser_setup.py — Configuración del navegador con proxy y geolocalización España
=================================================================================
Basado en el flujo del proyecto de referencia Bot_Orange.
"""

import random
from pathlib import Path


def crear_contexto_espana(playwright, proxy_config: dict = None):
    """
    Crea browser + contexto con geolocalización España.

    proxy_config: {
        "server": "http://ip:puerto" o "socks5://ip:puerto",
        "username": "...",
        "password": "..."
    }
    Si proxy_config es None, se lanza sin proxy.
    """
    launch_args = {
        "headless": False,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
    }

    browser = playwright.chromium.launch(**launch_args)

    context_args = {
        "timezone_id": "Europe/Madrid",
        "locale": "es-ES",
        "geolocation": {"longitude": -3.703790, "latitude": 40.416775},
        "permissions": ["geolocation"],
        "viewport": {"width": 1366, "height": 768},
        "user_agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
    }

    if proxy_config:
        context_args["proxy"] = {
            "server": proxy_config["server"],
        }
        if proxy_config.get("username"):
            context_args["proxy"]["username"] = proxy_config["username"]
        if proxy_config.get("password"):
            context_args["proxy"]["password"] = proxy_config["password"]

    context = browser.new_context(**context_args)

    # ── OPTIMIZACION: bloquear recursos pesados (imagenes, fuentes, media) ──
    # Pangea es texto/DOM; no se necesitan imagenes ni fuentes para extraer datos.
    # [IMPORTANTE] NO se bloquea CSS: el bot lee getComputedStyle(backgroundColor)
    # para detectar lineas activas/inactivas, asi que las hojas de estilo son necesarias.
    def _bloquear_recursos(route):
        try:
            if route.request.resource_type in ("image", "media", "font"):
                route.abort()
            elif "ayuda.orange.es" in route.request.url:
                # Bloquear navegacion accidental a paginas de ayuda
                # (clic en Herramientas > Centralita del menu de Pangea)
                route.abort()
            else:
                route.continue_()
        except Exception:
            try:
                route.continue_()
            except Exception:
                pass
    context.route("**/*", _bloquear_recursos)
    print("  [Browser] Bloqueo de recursos activo (image/media/font)")
    
    # ── BLINDAJE PERMANENTE: inyectar CSS anti-Herramientas en CADA pagina ──
    # Este script corre ANTES de que la pagina cargue, sobrevive a navegaciones.
    context.add_init_script("""
        const antiToolsStyle = document.createElement('style');
        antiToolsStyle.id = 'oratioo-blindaje-tools';
        antiToolsStyle.textContent = `
            .o-comp__tools-menu-container,
            div[ng-show="toolsCtrl.showMenu"] {
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }
            .o-comp__tools__select,
            button.o-comp__form-select--bold {
                pointer-events: none !important;
            }
        `;
        (document.head || document.documentElement).appendChild(antiToolsStyle);
    """)
    print("  [Browser] Blindaje anti-Herramientas instalado (init_script)")

    return browser, context


def parsear_proxy(linea: str) -> dict | None:
    """
    Parsea una línea de proxies.txt.
    Formatos aceptados:
      - ip:puerto:usuario:contraseña
      - http://usuario:contraseña@ip:puerto
      - ip:puerto (sin auth)
    """
    linea = linea.strip()
    if not linea or linea.startswith("#"):
        return None

    # Formato: ip:puerto:usuario:contraseña
    partes = linea.split(":")
    if len(partes) == 4:
        return {
            "server": f"http://{partes[0]}:{partes[1]}",
            "username": partes[2],
            "password": partes[3],
        }

    # Formato: http://usuario:pass@ip:puerto
    if "@" in linea:
        protocolo_resto = linea.split("://", 1)
        if len(protocolo_resto) == 2:
            resto = protocolo_resto[1]
            creds, host = resto.split("@", 1)
            user, passw = creds.split(":", 1)
            return {
                "server": f"http://{host}",
                "username": user,
                "password": passw,
            }

    # Formato simple: ip:puerto
    if len(partes) == 2:
        return {
            "server": f"http://{linea}",
        }

    return None


def cargar_proxies(archivo: str = None) -> list[dict]:
    """Carga todos los proxies desde proxies.txt."""
    if not archivo:
        archivo = str(Path(__file__).parent / "proxies.txt")

    proxies = []
    with open(archivo, "r", encoding="utf-8") as f:
        for linea in f:
            proxy = parsear_proxy(linea)
            if proxy:
                proxies.append(proxy)

    return proxies


def proxy_aleatorio(proxies: list[dict]) -> dict | None:
    """Selecciona un proxy al azar de la lista."""
    if not proxies:
        return None
    return random.choice(proxies)
