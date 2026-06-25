"""
login.py -- Automatización de login en Pangea Orange
=====================================================
FLUJO EXACTO (basado en Bot_Orange de referencia):
  1. Aceptar cookies
  2. Login: input[name='temp-username'] + input[name='temp-password'] + #submit-button
  3. Manejar "máximo de sesiones" si aparece
  4. Seleccionar marca: a.orange-box
  5. Abrir nuevo acto comercial
"""

import random
import time
import re
from playwright.sync_api import Page


# -- Excepciones ------------------------------------

class LoginError(Exception):
    pass

class SessionExpiredError(Exception):
    pass

class CriticalError(Exception):
    pass

class MaxSessionsError(LoginError):
    """Error especifico cuando se alcanza el maximo de sesiones en Pangea."""
    pass

class PangeaDownError(Exception):
    """Pangea esta completamente caida (chrome-error, ERR_TIMED_OUT)."""
    pass


# -- Contador de Pangea congelada --------------------
_frozen_count = 0
_FROZEN_LIMIT = 12  # despues de 12 seguidos sin respuesta -> F5

def _reset_frozen():
    global _frozen_count
    _frozen_count = 0

def _increment_frozen() -> bool:
    """Incrementa contador de congelamiento. Retorna True si alcanzo el limite."""
    global _frozen_count
    _frozen_count += 1
    return _frozen_count >= _FROZEN_LIMIT


# -- Helpers ----------------------------------------

def _escribir_como_humano(page: Page, selector: str, texto: str):
    """Escribe caracter por caracter con delay aleatorio + Tab para Angular."""
    campo = page.locator(selector).locator("visible=true").first
    campo.click()
    campo.fill("")
    for letra in texto:
        page.keyboard.type(letra, delay=random.randint(50, 150))
    # CRÍTICO: Tab para que Angular registre el cambio
    page.keyboard.press("Tab")
    page.wait_for_timeout(random.randint(300, 800))


def _extraer_texto(page: Page, selector: str) -> str:
    """Extrae texto de un elemento vía evaluate para bypassear Angular."""
    try:
        elemento = page.locator(selector).first
        texto = elemento.evaluate("el => el.textContent")
        return texto.strip().replace("\n", " ") if texto else "N/A"
    except Exception:
        return "N/A"


def _extraer_estado_linea(bloque) -> list:
    """Extrae los tags de estado de línea con su color para detectar activos vs inactivos.
    Args:
        bloque: Playwright locator del div.client-tariff-flex
    Retorna: lista de dicts {texto, color, activo}
    """
    estados = []
    try:
        tags = bloque.locator("ocs-line-status span.label")
        for k in range(tags.count()):
            tag = tags.nth(k)
            texto = tag.inner_text().strip()
            if not texto or texto == "Estado de línea:":
                continue
            # Leer estilo inline para detectar color
            style = tag.get_attribute("style") or ""
            color = tag.evaluate("el => getComputedStyle(el).backgroundColor") or ""
            # Detectar si está activo (no gris): rojo, naranja, amarillo, etc.
            activo = "grey" not in color.lower() and "rgb(204" not in color
            estados.append({"texto": texto, "color": color, "activo": activo})
    except Exception:
        pass
    return estados


def _extraer_detalle_linea(bloque, label_texto: str) -> str:
    """Extrae un dato específico de ocs-line-details por texto del label.
    Busca dentro de los divs client-tariff-section-data-info el que contenga
    el texto dado (ej: 'Permanencia', 'Consumo', 'Venta a Plazos') y devuelve
    el texto del strong asociado."""
    try:
        detalles = bloque.locator("ocs-line-details .client-tariff-section-data-info")
        for k in range(detalles.count()):
            detalle = detalles.nth(k)
            texto_completo = detalle.inner_text()
            if label_texto.lower() in texto_completo.lower():
                strong = detalle.locator("strong")
                if strong.count() > 0:
                    return strong.first.inner_text().strip()
                return texto_completo.strip()
    except Exception:
        pass
    return "N/A"


def parsear_fecha_permanencia(texto: str) -> str:
    """Intenta extraer una fecha del texto de permanencia.
    Formatos: 'Vence 15/09/2026', '15/09/2026', '2026-09-15', etc.
    Retorna string ISO o '' si no se puede parsear."""
    import re
    if not texto or texto == "N/A":
        return ""
    # dd/mm/yyyy o dd-mm-yyyy
    m = re.search(r'(\d{1,2})[/-](\d{1,2})[/-](\d{4})', texto)
    if m:
        dia, mes, anio = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{anio}-{mes}-{dia}"
    # yyyy-mm-dd
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', texto)
    if m:
        return m.group(0)
    return ""


def _extraer_campanas_tab(bloque, page, tab_nombre: str) -> list:
    """Hace click en una pestaña de campañas y extrae las cards visibles.
    Args:
        bloque: Playwright locator del div.client-tariff-flex
        page: instancia de página Playwright
        tab_nombre: texto del botón de la pestaña (ej: 'Cambio Tarifa', 'Bonos y Descuen.', 'SVA')
    Retorna: lista de dicts {tipo, texto}
    """
    campanas = []
    try:
        tab_bar = bloque.locator(".client-tariff-section-navs")
        if tab_bar.count() == 0:
            return campanas
        tab_btn = tab_bar.locator(f"button:has-text('{tab_nombre}')")
        if tab_btn.count() == 0:
            return campanas
        # Click en la pestaña
        try:
            tab_btn.first.click(timeout=4000)
            page.wait_for_timeout(150)
        except Exception:
            try:
                tab_btn.first.click(force=True, timeout=4000)
                page.wait_for_timeout(150)
            except Exception:
                return campanas
        # Extraer cards visibles
        cards_container = bloque.locator(".client-tariff-section-cards")
        if cards_container.count() > 0:
            cards = cards_container.locator(".card-tariff-minimal")
            for c_idx in range(cards.count()):
                card = cards.nth(c_idx)
                try:
                    label_el = card.locator(".card-tariff-label strong")
                    tipo = label_el.first.inner_text().strip() if label_el.count() > 0 else tab_nombre
                    info_el = card.locator(".card-tariff-info-text")
                    texto = info_el.first.inner_text().strip() if info_el.count() > 0 else card.inner_text().strip()
                    campanas.append({"tipo": tipo, "texto": texto})
                except Exception:
                    pass
    except Exception:
        pass
    return campanas


def _extraer_campanas_otros(bloque) -> list:
    """Extrae campañas del dropdown 'Otros' sin hacer click (cards ya visibles con label 'Otros')."""
    campanas = []
    try:
        cards_container = bloque.locator(".client-tariff-section-cards")
        if cards_container.count() == 0:
            return campanas
        cards = cards_container.locator(".card-tariff-minimal")
        for c_idx in range(cards.count()):
            card = cards.nth(c_idx)
            try:
                label_el = card.locator(".card-tariff-label strong")
                tipo = label_el.first.inner_text().strip() if label_el.count() > 0 else ""
                info_el = card.locator(".card-tariff-info-text")
                texto = info_el.first.inner_text().strip() if info_el.count() > 0 else ""
                if tipo and texto and tipo.lower() not in ("renove", "destacadas"):
                    campanas.append({"tipo": tipo, "texto": texto})
            except Exception:
                pass
    except Exception:
        pass
    return campanas


def _detectar_no_cliente_explicito(page: Page, es_telefono: bool = False) -> bool:
    """Verifica si Pangea muestra EXPLICITAMENTE que el cliente no existe.
    Solo retorna True si el texto de error es visible (no ng-hide).
    Para busqueda por telefono, verifica que el .msg-error este cerca
    del campo telefono, no del campo DNI."""
    textos_no_cliente = [
        "No se han encontrado datos",
        "No se han encontrado datos para este cliente",
    ]
    try:
        # Buscar en TODOS los .msg-error visibles (no ng-hide)
        msg_errors = page.locator(".msg-error")
        for i in range(msg_errors.count()):
            el = msg_errors.nth(i)
            try:
                if not el.is_visible():
                    continue
                texto = el.inner_text().strip()
                for patron in textos_no_cliente:
                    if patron in texto:
                        # Si es busqueda por telefono, verificar ubicacion
                        if es_telefono:
                            try:
                                padre = el.locator("..")
                                msisdn_input = padre.locator("input[ng-model='locatorCtrl.inputMsisdn']")
                                if msisdn_input.count() == 0:
                                    continue  # es el .msg-error del DNI, no del telefono
                            except Exception:
                                pass
                        return True
            except Exception:
                continue
        # Tambien buscar spans con el texto (fuera de .msg-error)
        for patron in textos_no_cliente:
            spans = page.locator(f"span.txt:has-text('{patron}')")
            for i in range(spans.count()):
                try:
                    if spans.nth(i).is_visible():
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


# -- Login ------------------------------------------

def manejar_cookies_flexible(page: Page):
    """Acepta el banner de cookies."""
    try:
        boton = page.locator("button:has-text('Aceptar')").first
        boton.wait_for(state="visible", timeout=5000)
        boton.click()
        print("  [Login] Cookies aceptadas")
    except Exception:
        pass


def manejar_maximo_sesiones(page: Page) -> bool:
    """Detecta maximo de sesiones en .mensaje_error o get_by_text."""
    try:
        # Buscar en mensaje_error
        for el in page.locator(".mensaje_error").all():
            if el.is_visible():
                t = el.inner_text().strip()
                if ("maximo" in t.lower() or "máximo" in t.lower()) and "sesiones" in t.lower():
                    print("  [Login] [!!] MAX SESIONES detectado.")
                    return True
        # Fallback: get_by_text
        if page.get_by_text("maximo permitido de sesiones").is_visible(timeout=2000):
            print("  [Login] [!!] MAX SESIONES detectado.")
            return True
    except Exception:
        pass
    return False


def realizar_login(page: Page, usuario: str = None, password: str = None):
    """Login en Orange con los selectores exactos del proyecto de referencia."""
    from dotenv import load_dotenv
    import os
    load_dotenv()

    usuario = usuario or os.getenv("ORANGE_USER", "")
    password = password or os.getenv("ORANGE_PASS", "")

    if not usuario or not password:
        raise LoginError("ORANGE_USER y ORANGE_PASS deben estar en .env")

    print(f"  [Login] Iniciando sesión...")

    try:
        # Esperar campo de usuario (temp-username es el input Angular)
        page.wait_for_selector("input[name='temp-username']", timeout=20000)
        _escribir_como_humano(page, "input[name='temp-username']", usuario)
        _escribir_como_humano(page, "input[name='temp-password']", password)

        # Click en botón de login
        page.click("#submit-button")
        page.wait_for_timeout(10000)

        # Manejar posible modal de maximo de sesiones
        if manejar_maximo_sesiones(page):
            raise MaxSessionsError("Maximo de sesiones alcanzado")

        # Esperar que aparezca la pagina post-login
        try:
            page.wait_for_selector(".brands", timeout=10000)
        except Exception:
            pass
        # Verificar exito por cualquiera de estos indicadores
        for sel in ["a.orange-box", "button[title='Cambiar cliente']", "button:has-text('Nuevo acto comercial')"]:
            try:
                if page.locator(sel).first.is_visible(timeout=3000):
                    print("  [Login] [OK] Login exitoso")
                    return
            except Exception:
                pass
        # Si llegamos aqui, intentar .brands como ultimo recurso
        try:
            page.wait_for_selector(".brands", timeout=5000)
        except Exception:
            raise Exception("No se detecto pagina post-login")

    except Exception as e:
        if isinstance(e, LoginError):
            raise  # re-raise MaxSessionsError etc sin re-wrappear
        raise LoginError(f"Fallo en login: {e}")


def seleccionar_marca_orange(page: Page):
    """Selecciona la marca Orange en el selector de marcas."""
    print("  [Login] Seleccionando marca Orange...")
    try:
        selector = "a.orange-box"
        page.wait_for_selector(selector, state="visible", timeout=20000)
        page.wait_for_timeout(2000)
        page.click(selector)
        page.wait_for_selector("#orange-container", timeout=30000)
        print("  [Login] [OK] Marca Orange seleccionada")
    except Exception as e:
        raise LoginError(f"Fallo al seleccionar marca: {e}")


def abrir_nuevo_acto_comercial(page: Page):
    """Abre un nuevo acto comercial con múltiples estrategias.
    
    Estrategias (en orden):
    1. Click normal en 'Nuevo acto comercial' -> 'Tarifas' -> 'Crear'
    2. Force click si el elemento no es visible
    3. Navegación directa a la URL de Tarifas (más fiable)
    """
    print("  [Login] Preparando entorno (nuevo acto comercial)...")
    
    def _click_tarifas():
        # Hover en Nuevo acto comercial para desplegar menu
        nac = page.locator("button:has-text('Nuevo acto comercial')")
        nac.wait_for(state="visible", timeout=15000)
        try:
            nac.first.hover()
            page.wait_for_timeout(500)
        except Exception:
            pass
        nac.first.click()
        page.wait_for_timeout(3000)
        
        # Estrategia 1: hover + click
        tarifas = page.locator("li:has-text('Tarifas')")
        try:
            tarifas.first.wait_for(state="visible", timeout=10000)
            tarifas.first.hover()
            page.wait_for_timeout(300)
            tarifas.first.click()
            return True
        except Exception:
            pass
        
        # Estrategia 2: force click (aunque no sea visible)
        try:
            tarifas.first.click(force=True, timeout=5000)
            return True
        except Exception:
            pass
        
        # Estrategia 3: click via JavaScript
        try:
            page.evaluate("""() => {
                const el = document.querySelector('li:has-text(\"Tarifas\")');
                if (el) { el.click(); return true; }
                // Buscar enlaces con texto Tarifas
                const links = document.querySelectorAll('a');
                for (const a of links) {
                    if (a.textContent.includes('Tarifas')) { a.click(); return true; }
                }
                return false;
            }""")
            page.wait_for_timeout(2000)
            return True
        except Exception:
            pass
        
        return False
    
    try:
        if not _click_tarifas():
            raise LoginError("No se pudo hacer clic en Tarifas")

        btn_crear = page.locator("button:has-text('Crear')").last
        btn_crear.wait_for(state="visible", timeout=20000)
        try:
            btn_crear.hover()
            page.wait_for_timeout(300)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        btn_crear.click()

        # Esperar que aparezca el botón de cambiar cliente
        page.wait_for_selector("button[title='Cambiar cliente']", timeout=30000)
        
        # -- BLINDAJE: inyectar CSS anti-Herramientas desde el inicio --
        _blindar_contra_tools_dropdown(page)
        
        print("  [Login] [OK] Entorno listo")
    except Exception as e:
        raise LoginError(f"Fallo al armar entorno: {e}")


# -- Extracción de datos del cliente ----------------

def _hay_toast_error(page) -> bool:
    """Detecta y cierra el toast de error de Orange.
    Cierra el toast automaticamente si esta presente
    para que no bloquee el boton Cambiar cliente."""
    try:
        toast = page.locator(".message-relevant.error")
        if toast.count() == 0:
            return False
        if toast.first.is_visible(timeout=1000):
            try:
                close_btn = toast.locator(".btn-close")
                if close_btn.count() > 0:
                    close_btn.first.click(force=True, timeout=2000)
                    page.wait_for_timeout(500)
            except:
                pass
            return True
    except Exception:
        pass
    return False

def _abrir_cambiar_cliente(page):
    """Hace clic en Cambiar cliente para dejar el modal listo para el siguiente DNI."""
    try:
        page.locator("button[title='Cambiar cliente']").first.click(force=True, timeout=5000)
        page.wait_for_timeout(1000)
    except Exception:
        pass


def _blindar_contra_tools_dropdown(page: Page):
    """Inyecta CSS para deshabilitar el dropdown de 'Herramientas' en el header.
    
    El boton 'Herramientas' en el header de Pangea abre un dropdown con links como
    'Centralita LOVE', 'ARPA', etc. al hacer hover o click.
    Si el bot accidentalmente activa este dropdown y hace click en un link,
    navega fuera de Pangea y pierde la sesion. Este blindaje lo previene."""
    try:
        page.add_style_tag(content="""
            /* BLINDAJE: deshabilitar dropdown de Herramientas */
            .o-comp__tools-menu-container,
            div[ng-show="toolsCtrl.showMenu"] {
                display: none !important;
                visibility: hidden !important;
                pointer-events: none !important;
            }
            /* Deshabilitar hover/click en el boton Herramientas */
            .o-comp__tools__select,
            button.o-comp__form-select--bold {
                pointer-events: none !important;
            }
        """)
        print("  [Blindaje] CSS anti-Herramientas inyectado")
    except Exception as e:
        print(f"  [Blindaje] [WARN] No se pudo inyectar CSS: {e}")


def _verificar_no_navego_fuera(page: Page, dni_actual: str = "") -> bool:
    """Verifica que seguimos en Pangea y no navegamos a una pagina externa.
    Retorna True si todo OK, False si detecto navegacion externa.
    Lanza PangeaDownError si detecta que Pangea esta caida (chrome-error)."""
    try:
        url = page.url
        if "pangea.orange.es" not in url:
            # Detectar Pangea caida (chrome-error://chromewebdata/)
            if "chrome-error" in url or "chromewebdata" in url:
                print(f"  [FATAL] [!!] PANGEA CAIDA detectada para DNI {dni_actual}!")
                print(f"  [FATAL] URL: {url}")
                raise PangeaDownError(f"Pangea no disponible (chrome-error): {url}")
            print(f"  [ALARMA] [!!] NAVEGACION FUERA DE PANGEA detectada para DNI {dni_actual}!")
            print(f"  [ALARMA] URL actual: {url}")
            # Intentar volver
            try:
                page.go_back()
                page.wait_for_timeout(2000)
                print(f"  [ALARMA] go_back() ejecutado, nueva URL: {page.url}")
            except Exception:
                print(f"  [ALARMA] No se pudo hacer go_back()")
            return False
        return True
    except PangeaDownError:
        raise
    except Exception:
        return True  # Si ni siquiera podemos leer la URL, asumimos OK para no frenar


def extraer_datos_cliente(page: Page, numero: str, buscar_por_dni: bool = True,
                           modal_ya_abierto: bool = False):
    """
    Busca un cliente por DNI (o teléfono) y extrae todos sus datos.

    Args:
        modal_ya_abierto: Si True, el modal de búsqueda ya está abierto
                          ("no es cliente" del DNI anterior). Solo escribe
                          el DNI y busca, sin reabrir el modal.

    Retorna lista de dicts (una fila por línea del cliente).
    """
    max_intentos = 2

    for intento in range(max_intentos):
        # -- Auto-detectar tipo de busqueda: DNI vs telefono --
        es_telefono = numero.replace(' ', '').replace('-', '').isdigit() and len(numero.replace(' ', '').replace('-', '')) == 9
        print(f"  [Extracción] Buscando: {numero} (Intento {intento+1}) {'[TEL]' if es_telefono else '[DNI]'}")
        try:
            # -- BLINDAJE 0: Verificar que no navegamos fuera --
            if not _verificar_no_navego_fuera(page, dni_actual=numero):
                print(f"  [Extracción] [!!] Navegacion externa detectada -- abortando cliente {numero}")
                return []

            # -- BLINDAJE 1: cubierto por add_init_script del contexto (browser_setup) --
            # (se elimina la inyeccion por-cliente: era redundante y costaba tiempo en cada DNI)

            # -- 1. ABRIR MODAL (igual para DNI y telefono) ----------
            if modal_ya_abierto:
                # Modal abierto del DNI anterior ("no es cliente")
                selector_documento = "input[name='document']"
                try:
                    page.wait_for_selector(selector_documento, state="visible", timeout=5000)
                except Exception:
                    selector_documento = "input[ng-model='locatorCtrl.inputDocument']"
                    page.wait_for_selector(selector_documento, state="visible", timeout=5000)
            else:
                # -- Abrir modal de busqueda --
                btn_cambiar = page.locator("button[title='Cambiar cliente']")
                btn_cambiar.wait_for(state="visible", timeout=15000)
                btn_cambiar.click(force=True)

                # Esperar a que el modal cargue
                page.wait_for_selector("input[name='document']", state="visible", timeout=10000)

            # -- 2. ESCRIBIR EN EL CAMPO CORRECTO (DNI vs Telefono) --
            if es_telefono:
                # TELFONO: escribir en input ng-model locatorCtrl.inputMsisdn
                campo = page.locator("input[ng-model='locatorCtrl.inputMsisdn']").first
                campo.wait_for(state="visible", timeout=5000)
                campo.click()
                campo.fill("")
                campo.fill(numero.replace(' ', '').replace('-', ''))
                campo.evaluate(
                    "el => { el.dispatchEvent(new Event('input', { bubbles: true })); "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); }"
                )
                print("  [Extracción] Telefono escrito en modal")
            else:
                # DNI: escribir en input[name='document']
                selector_documento = "input[name='document']"
                try:
                    page.wait_for_selector(selector_documento, state="visible", timeout=3000)
                except Exception:
                    selector_documento = "input[ng-model='locatorCtrl.inputDocument']"
                campo = page.locator(selector_documento).first
                campo.click()
                campo.fill("")
                campo.fill(numero)
                campo.evaluate(
                    "el => { el.dispatchEvent(new Event('input', { bubbles: true })); "
                    "el.dispatchEvent(new Event('change', { bubbles: true })); }"
                )

            # -- 3. CLICK EN "Buscar cliente" --
            page.wait_for_timeout(random.randint(150, 350))
            btn_buscar = page.locator("button:has-text('Buscar cliente')").last
            btn_buscar.click(force=True)

            # BLINDAJE POST-CLICK: verificar que no abrimos Centralita LOVE u otra pagina
            if not _verificar_no_navego_fuera(page, dni_actual=numero):
                print(f"  [Extracción] [!!] Tras click Buscar cliente se navego fuera -- abortando {numero}")
                return []

            # -- BLINDAJE: esperar que el modal se cierre (max 5s) --
            print("  [Extracción] Verificando procesamiento...")
            try:
                btn_buscar.wait_for(state="hidden", timeout=5000)
            except Exception:
                # Puede que el modal no se cierre si no es cliente
                pass

            # SEGUNDO BLINDAJE: verificar que seguimos en Pangea
            if not _verificar_no_navego_fuera(page, dni_actual=numero):
                print(f"  [Extracción] [!!] Navegacion externa tras procesar {numero} -- retornando vacio")
                return []

            # DETECTAR PYME (empresa) -- Pangea no cierra el modal
            try:
                pyme_matches = page.locator(".msg-error:has-text('Cliente PYME')")
                pyme_visible = False
                for j in range(pyme_matches.count()):
                    if pyme_matches.nth(j).is_visible():
                        pyme_visible = True
                        break
                if pyme_visible:
                    print(f"  [Extracción] [PYME] {numero} es empresa -- cerrando modal")
                    try:
                        close_btn = page.locator("button.close[data-dismiss='modal']").last
                        if close_btn.count() > 0:
                            close_btn.click(force=True, timeout=3000)
                            page.wait_for_timeout(500)
                    except Exception:
                        pass
                    return [{
                        "DNI": numero,
                        "Nombre": "CLIENTE PYME",
                        "Direccion": "N/A",
                        "Seg Fijo": "N/A",
                        "Seg Movil": "N/A",
                        "Paquete": "N/A",
                        "Linea": numero,
                        "es_cima": False,
                        "tiene_renove_mixto": False,
                        "variante_renove": "N/A",
                        "tiene_tv": False,
                        "es_principal": False,
                        "etiquetas": [],
                        "activo_desde": "N/A",
                        "producto": "N/A",
                        "estado_linea": [],
                        "permanencia": "N/A",
                        "consumo": "N/A",
                        "venta_plazos": "N/A",
                        "campanas_extra": [],
                        "_modal_abierto": False,
                    }]
            except Exception:
                pass

            # DETECTAR GGCC (Gran Cuenta) -- consulta Siebel 8
            try:
                ggcc_matches = page.locator(".msg-error:has-text('Cliente GGCC')")
                ggcc_visible = False
                for j in range(ggcc_matches.count()):
                    if ggcc_matches.nth(j).is_visible():
                        ggcc_visible = True
                        break
                if ggcc_visible:
                    print(f"  [Extraccion] [GGCC] {numero} es Gran Cuenta -- cerrando modal")
                    try:
                        close_btn = page.locator("button.close[data-dismiss='modal']").last
                        if close_btn.count() > 0:
                            close_btn.click(force=True, timeout=3000)
                            page.wait_for_timeout(500)
                    except Exception:
                        pass
                    return [{
                        "DNI": numero,
                        "Nombre": "CLIENTE GGCC",
                        "Direccion": "N/A",
                        "Seg Fijo": "N/A",
                        "Seg Movil": "N/A",
                        "Paquete": "N/A",
                        "Linea": numero,
                        "es_cima": False,
                        "tiene_renove_mixto": False,
                        "variante_renove": "N/A",
                        "tiene_tv": False,
                        "es_principal": False,
                        "etiquetas": [],
                        "activo_desde": "N/A",
                        "producto": "N/A",
                        "estado_linea": [],
                        "permanencia": "N/A",
                        "consumo": "N/A",
                        "venta_plazos": "N/A",
                        "campanas_extra": [],
                        "_modal_abierto": False,
                    }]
            except Exception:
                pass

            # DETECTAR MAXIMO DE LINEAS ("Este cliente supera el maximo de lineas permitidas")
            try:
                max_lineas_matches = page.locator(".msg-error:has-text('supera el maximo de lineas permitidas')")
                max_lineas_visible = False
                for j in range(max_lineas_matches.count()):
                    if max_lineas_matches.nth(j).is_visible():
                        max_lineas_visible = True
                        break
                if max_lineas_visible:
                    print(f"  [Extraccion] [MAX-LINEAS] {numero} supera maximo de lineas -- cerrando modal")
                    try:
                        close_btn = page.locator("button.close[data-dismiss='modal']").last
                        if close_btn.count() > 0:
                            close_btn.click(force=True, timeout=3000)
                            page.wait_for_timeout(500)
                    except Exception:
                        pass
                    return [{
                        "DNI": numero,
                        "Nombre": "CLIENTE MAX LINEAS",
                        "Direccion": "N/A",
                        "Seg Fijo": "N/A",
                        "Seg Movil": "N/A",
                        "Paquete": "N/A",
                        "Linea": numero,
                        "es_cima": False,
                        "tiene_renove_mixto": False,
                        "variante_renove": "N/A",
                        "tiene_tv": False,
                        "es_principal": False,
                        "etiquetas": [],
                        "activo_desde": "N/A",
                        "producto": "N/A",
                        "estado_linea": [],
                        "permanencia": "N/A",
                        "consumo": "N/A",
                        "venta_plazos": "N/A",
                        "campanas_extra": [],
                        "_modal_abierto": False,
                    }]
            except Exception:
                pass

            # === DETECTAR "NO ES CLIENTE" (SOLO SI PANGEA LO DICE EXPLICITAMENTE) ===
            if _detectar_no_cliente_explicito(page, es_telefono):
                _reset_frozen()
                print(f"  [Extracción] [FAIL] {numero} NO ES CLIENTE (explicito)")
                return [{
                    "DNI": numero,
                    "Nombre": "NO ES CLIENTE",
                    "Direccion": "N/A",
                    "Seg Fijo": "N/A",
                    "Seg Movil": "N/A",
                    "Paquete": "N/A",
                    "Linea": numero,
                    "es_cima": False,
                    "tiene_renove_mixto": False,
                    "variante_renove": "N/A",
                    "tiene_tv": False,
                    "es_principal": False,
                    "etiquetas": [],
                    "activo_desde": "N/A",
                    "producto": "N/A",
                    "estado_linea": [],
                    "permanencia": "N/A",
                    "consumo": "N/A",
                    "venta_plazos": "N/A",
                    "campanas_extra": [],
                    "_modal_abierto": True,
                }]

            # === DETECTAR PANGEA CONGELADA (modal abierto SIN texto de error) ===
            try:
                if btn_buscar.is_visible():
                    # Modal abierto pero SIN texto explicito de no_cliente
                    # -> Pangea no respondio (congelada)
                    if _increment_frozen():
                        print(f"  [Extracción] [!!] {_FROZEN_LIMIT} DNIs sin respuesta de Pangea. Haciendo F5...")
                        _reset_frozen()
                        page.reload(timeout=30000, wait_until="domcontentloaded")
                        page.wait_for_timeout(3000)
                        # Verificar si Pangea cargo tras F5
                        current_url = page.url
                        if "pangea.orange.es" not in current_url:
                            print(f"  [Extracción] [FATAL] Pangea no disponible tras F5 (URL: {current_url})")
                            raise Exception("Pangea no disponible tras F5")
                        # Reabrir modal de busqueda
                        print("  [Extracción] Pangea respondio tras F5. Reabriendo modal...")
                        try:
                            btn_cambiar = page.locator("button[title='Cambiar cliente']")
                            btn_cambiar.wait_for(state="visible", timeout=10000)
                            btn_cambiar.click(force=True)
                            page.wait_for_selector("input[name='document']", state="visible", timeout=10000)
                        except Exception:
                            pass
                    # Retornar vacio -> worker lo marca como error y reintenta luego
                    print(f"  [Extracción] [WARN] {numero}: Pangea no respondio (modal abierto sin error). Frozen: {_frozen_count}/{_FROZEN_LIMIT}")
                    return []
            except Exception:
                pass

            # === DETECTAR ERROR "No se han podido recuperar campañas" ===
            if _hay_toast_error(page):
                print(f"  [Extracción] [FAIL] {numero}: error campañas -- Cambiar cliente y siguiente")
                _abrir_cambiar_cliente(page)
                return [{
                    "DNI": numero,
                    "Nombre": "ERROR CAMPANAS",
                    "Direccion": "N/A",
                    "Seg Fijo": "N/A",
                    "Seg Movil": "N/A",
                    "Paquete": "N/A",
                    "Linea": numero,
                    "es_cima": False,
                    "tiene_renove_mixto": False,
                    "variante_renove": "N/A",
                    "tiene_tv": False,
                    "es_principal": False,
                    "etiquetas": [],
                    "activo_desde": "N/A",
                    "producto": "N/A",
                    "estado_linea": [],
                    "permanencia": "N/A",
                    "consumo": "N/A",
                    "venta_plazos": "N/A",
                    "campanas_extra": [],
                    "_modal_abierto": True,
                }]

            print("  [Extracción] Cargando ficha de cliente...")
            page.wait_for_timeout(300)
            page.wait_for_selector(".mod-barclient__container-data", timeout=20000)

            # -- DETECTAR CIMA GLOBAL (barra superior) --
            cima_global = False
            try:
                cima_btn = page.locator(".mod-barclient__container-lines-cima-btn")
                if cima_btn.count() > 0:
                    texto_cima_btn = cima_btn.first.inner_text()
                    cima_global = "isCima" in texto_cima_btn or "CIMA" in texto_cima_btn.upper()
            except Exception:
                pass

            # -- 2. DATOS CABECERA ---------------------
            nombre = _extraer_texto(page, ".tooltip-text.name strong")
            dni = _extraer_texto(page, "span.font-xxs.p-r-10")

            # BLINDAJE ANTI-DUPLICACION (solo para busqueda por DNI)
            dni_page_limpio = dni.strip().upper().replace("-", "").replace(".", "").replace(" ", "")
            dni_buscado_limpio = numero.strip().upper().replace("-", "").replace(".", "").replace(" ", "")
            if not es_telefono and dni_page_limpio and dni_buscado_limpio and dni_page_limpio not in ("N/A", "") and dni_page_limpio != dni_buscado_limpio:
                print(f"  [Extracción] [FAIL] DNI no coincide: buscado={numero} vs pagina={dni} -- modal no cargo")
                raise Exception(f"DNI mismatch: buscado {numero} != pagina {dni}")

            # SKIP DUPLICADOS: busqueda por telefono de cliente ya procesado
            if es_telefono and dni_page_limpio and dni_page_limpio not in ("N/A", ""):
                try:
                    import requests
                    import os as _os
                    from pathlib import Path as _Path
                    from dotenv import load_dotenv as _ld
                    _ld(_Path(__file__).parent.parent / '.env')
                    r = requests.get(
                        f"{_os.getenv('BOT_API_URL', 'http://localhost:3000')}/api/clientes/{dni_page_limpio}",
                        headers={"x-bot-api-key": _os.getenv('BOT_API_KEY', 'oratioo-bot-internal-key')},
                        timeout=5,
                    )
                    if r.ok and r.json():
                        print(f"  [Extracción] [SKIP] Cliente {dni_page_limpio} ya procesado -- omitiendo")
                        return [{"DNI": dni_page_limpio, "Nombre": "YA_PROCESADO", "_skip": True,
                                "Direccion": "N/A", "Seg Fijo": "N/A", "Seg Movil": "N/A",
                                "Paquete": "N/A", "Linea": numero,
                                "es_cima": False, "tiene_renove_mixto": False, "variante_renove": "N/A",
                                "tiene_tv": False, "es_principal": False, "etiquetas": [],
                                "activo_desde": "N/A", "producto": "N/A", "estado_linea": [],
                                "permanencia": "N/A", "consumo": "N/A", "venta_plazos": "N/A",
                                "campanas_extra": [], "notificacion_pack": "", "_modal_abierto": False}]
                except Exception:
                    pass  # Si falla la API, seguir normalmente
            direccion = _extraer_texto(page, ".tooltip-text.address")
            seg_fijo = _extraer_texto(page, "div.font-xxs:has-text('Seg. Fijo:') strong")
            seg_movil = _extraer_texto(page, "div.font-xxs:has-text('Seg. Móvil:') strong")
            paquete = _extraer_texto(page, ".client-tariff-title .font-lg")

            # -- Extraer notificación de pack --
            notificacion_pack = ""
            try:
                notif_el = page.locator(".notification-container .message-relevant.info p.title")
                if notif_el.count() > 0:
                    notificacion_pack = notif_el.first.inner_text().strip()
                    print(f"  [Extracción] Notificacion: {notificacion_pack}")
            except Exception:
                pass

            print(f"  [Extracción] Cliente: {nombre} | DNI: {dni} | Paquete: {paquete}")
            print(f"  [Extracción] Dirección: {direccion}")

            # === TOAST ERROR ("No se han podido recuperar campañas") -- SALTAR DNI ===
            if _hay_toast_error(page):
                print(f"  [Extracción] [FAIL] {numero}: error campañas -- Cambiar cliente y siguiente")
                _abrir_cambiar_cliente(page)
                return [{
                    "DNI": numero,
                    "Nombre": "ERROR CAMPANAS",
                    "Direccion": direccion if direccion != "N/A" else "N/A",
                    "Seg Fijo": "N/A",
                    "Seg Movil": "N/A",
                    "Paquete": "N/A",
                    "Linea": numero,
                    "es_cima": False,
                    "tiene_renove_mixto": False,
                    "variante_renove": "N/A",
                    "tiene_tv": False,
                    "es_principal": False,
                    "etiquetas": [],
                    "activo_desde": "N/A",
                    "producto": "N/A",
                    "estado_linea": [],
                    "permanencia": "N/A",
                    "consumo": "N/A",
                    "venta_plazos": "N/A",
                    "campanas_extra": [],
                    "_modal_abierto": True,
                }]

            # -- 3. BUCLE DE LÍNEAS CON PAGINACIÓN -----
            lineas_finales = []
            lineas_vistas = set()  # Anti-loop paginacion
            hay_mas_paginas = True
            pagina_actual = 1

            while hay_mas_paginas:
                print(f"  [Extracción] Página {pagina_actual} de líneas...")
                bloques = page.locator(".client-tariff-flex")

                for i in range(bloques.count()):
                    bloque = bloques.nth(i)
                    if not bloque.locator(".line-section .color-primary strong").is_visible():
                        continue

                    # -- Paquete de ESTE tariff (vía XPath ancestor) --
                    paquete_tariff = paquete  # fallback
                    try:
                        # [!!] contains(@class,'client-tariff') también atrapa <div class="mod-client-tariff">
                        # -> usar word-boundary match para pillar solo el div.tariff real, no el wrapper
                        tariff_parent = bloque.locator("xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' client-tariff ')]")
                        if tariff_parent.count() > 0:
                            # DIAG: intentar varios selectores para pillar el título del tariff
                            titulo_el = tariff_parent.first.locator(".client-tariff-title .font-lg")
                            if titulo_el.count() == 0:
                                # Alternativa: buscar cualquier .font-lg dentro del ancestor
                                titulo_el = tariff_parent.first.locator(".font-lg")
                            if titulo_el.count() == 0:
                                # Último intento: h2, h3, o cualquier heading fuerte
                                titulo_el = tariff_parent.first.locator("h2, h3, .tariff-title, [class*='title']")
                            if titulo_el.count() > 0:
                                paquete_tariff = titulo_el.first.inner_text().strip()
                            else:
                                print(f"      [DIAG] Ancestor encontrado pero sin título")
                        else:
                            print(f"      [DIAG] XPath ancestor no encontrado para este bloque")
                    except Exception as e:
                        print(f"      [DIAG] Error ancestor lookup: {e}")

                    num_linea = bloque.locator(
                        ".line-section .color-primary strong"
                    ).inner_text().strip()
                    # 🔄 Anti-loop: si ya vimos esta línea, Orange está repitiendo páginas
                    if num_linea in lineas_vistas:
                        print(f"    🛑 Línea {num_linea} repetida -- loop de paginación. Saliendo.")
                        hay_mas_paginas = False
                        break
                    lineas_vistas.add(num_linea)
                    print(f"    -> Línea: {num_linea} | Tariff: {paquete_tariff}")

                    # -- Extraer etiquetas reales del heading (CIMA, TV, Principal, etc.) --
                    try:
                        heading = bloque.locator(".client-tariff-heading")
                        labels = heading.locator("span.label")
                        etiquetas = [labels.nth(k).inner_text().strip() for k in range(labels.count())]
                        texto_completo = heading.first.inner_text()
                    except Exception:
                        etiquetas = []
                        texto_completo = ""
                    es_cima = "CIMA" in etiquetas or cima_global
                    tiene_tv = "TV" in etiquetas
                    es_principal = "Principal" in etiquetas
                    # Extraer fecha activo desde
                    match_fecha = re.search(r'Activo desde\s+(\d{2}/\d{2}/\d{4})', texto_completo)
                    activo_desde = match_fecha.group(1) if match_fecha else "N/A"

                    # -- NUEVO: Extraer producto de la línea --
                    producto_linea = "N/A"
                    try:
                        strongs = bloque.locator(".line-section strong")
                        if strongs.count() >= 2:
                            producto_linea = strongs.nth(1).inner_text().strip()
                    except Exception:
                        pass

                    # -- NUEVO: Extraer estado de línea con colores --
                    estado_linea = _extraer_estado_linea(bloque)

                    # -- NUEVO: Extraer permanencia, consumo, VAPs --
                    permanencia = _extraer_detalle_linea(bloque, "Permanencia")
                    # Extraer fecha exacta de permanencia para scoring
                    permanencia_fecha = parsear_fecha_permanencia(permanencia)
                    consumo = _extraer_detalle_linea(bloque, "Consumo")
                    venta_plazos = _extraer_detalle_linea(bloque, "Venta a Plazos")

                    # -- Detectar Renove: click en PESTAÑA "Renove" (no en tarjeta!) --
                    tiene_rm = False
                    variante_renove = "N/A"
                    renove_texto_raw = ""
                    renove_timeout = False
                    heading_text = ""
                    tiene_rm_heading = False
                    try:
                        heading_text = bloque.locator(".client-tariff-heading").first.inner_text()
                        tiene_rm_heading = bool(re.search(r'\b(Renove|MIXTO)\b', heading_text, re.IGNORECASE))
                    except Exception:
                        pass

                    try:
                        # Buscar la BARRA DE PESTAÑAS de esta línea
                        tab_bar = bloque.locator(".client-tariff-section-navs")
                        if tab_bar.count() > 0:
                            # Encontrar el botón "Renove" en los tabs
                            renove_tab_btn = tab_bar.locator("button:has-text('Renove')")
                            if renove_tab_btn.count() > 0:
                                print(f"      [RENOVE] Click en pestaña de navegación 'Renove'...")
                                try:
                                    renove_tab_btn.first.click(timeout=5000)
                                    page.wait_for_timeout(200)
                                except Exception:
                                    try:
                                        renove_tab_btn.first.click(force=True, timeout=5000)
                                        page.wait_for_timeout(200)
                                    except Exception:
                                        pass

                                # Leer el contenido de la tarjeta Renove (card-tariff-minimal)
                                texto_card = ""
                                try:
                                    cards_container = bloque.locator(".client-tariff-section-cards")
                                    if cards_container.count() > 0:
                                        # Buscar la card con label "Renove"
                                        renove_card = cards_container.locator(".card-tariff-minimal")
                                        for c_idx in range(renove_card.count()):
                                            card = renove_card.nth(c_idx)
                                            # Leer info-text directamente (puede no tener label cuando tab está activo)
                                            txt_el = card.locator(".card-tariff-info-text")
                                            if txt_el.count() > 0:
                                                txt = txt_el.first.inner_text().strip()
                                                # Si contiene RENOVE/MIXTO/MULTI, es la card que buscamos
                                                if re.search(r'\b(RENOVE|MIXTO|MULTIDISPOSITIVO)\b', txt.upper()):
                                                    texto_card = txt
                                                    break
                                                # Si no encontramos con filtro, guardar la primera y seguir buscando
                                                if not texto_card:
                                                    texto_card = txt
                                            else:
                                                txt = card.inner_text().strip()
                                                if "renove" in txt.upper():
                                                    texto_card = txt
                                                    break
                                                if not texto_card:
                                                    texto_card = txt
                                except Exception:
                                    pass

                                texto_up = texto_card.upper() if texto_card else ""
                                # [!!] Solo marcar Renove si HAY contenido real en la card
                                tiene_rm = bool(texto_card and re.search(r'\b(RENOVE|MIXTO|MULTIDISPOSITIVO)\b', texto_up))

                                if "RENOVE MIXTO" in texto_up or "MIXTO" in texto_up:
                                    if "MÁXIMO DESCUENTO" in texto_up or "MAXIMO DESCUENTO" in texto_up:
                                        variante_renove = "Renove mixto al mejor precio con máximo descuento"
                                    elif "CON DESCUENTO" in texto_up:
                                        variante_renove = "Renove mixto al mejor precio con descuento"
                                    elif "MEJOR PRECIO" in texto_up:
                                        variante_renove = "Renove mixto al mejor precio"
                                    else:
                                        variante_renove = "Renove mixto"
                                elif "MULTIDISPOSITIVO" in texto_up:
                                    variante_renove = "Renove Multidispositivo"
                                elif texto_card:
                                    variante_renove = f"Renove ({texto_card})"
                                # Si no hay texto, NO poner "Renove" a secas (pisaría datos válidos de otras líneas)
                                # mejor dejar "N/A" -- la línea no tiene Renove visible

                                print(f"      [RENOVE] Texto: {texto_card[:80] if texto_card else '(vacio)'} | -> {variante_renove}")
                                # Guardar también el texto original en campanas_extra para mostrarlo en la UI
                                renove_texto_raw = texto_card.strip() if texto_card else variante_renove
                            else:
                                print(f"      [RENOVE] No hay pestaña 'Renove' en la barra de tabs")
                        else:
                            print(f"      [RENOVE] No hay barra de pestañas en esta línea")
                    except Exception as e:
                        print(f"      [RENOVE] Error: {e}")

                    # -- FALLBACK heading --
                    if not tiene_rm and tiene_rm_heading:
                        variante_renove = "Renove (detectado en heading)"
                        print(f"      [RENOVE] Detectado en heading: {heading_text[:80]}")
                        tiene_rm = True

                    if renove_timeout:
                        raise Exception(f"Renove no cargó para {numero}")

                    # -- NUEVO: Extraer campañas adicionales (Cambio Tarifa, Bonos, SVA, Otros) --
                    campanas_extra = []
                    # Agregar Renove como campaña para que aparezca en la columna derecha de la UI
                    if tiene_rm and (renove_texto_raw or variante_renove not in ("N/A", "")):
                        campanas_extra.append({"tipo": "Renove", "texto": renove_texto_raw or variante_renove})
                    # Solo si la barra de tabs existe
                    try:
                        tab_bar_camp = bloque.locator(".client-tariff-section-navs")
                        if tab_bar_camp.count() > 0:
                            # Orden Orange: Destacadas -> Renove(ya) -> Bonos -> Cambio Tarifa -> SVA -> Otros
                            bonos = _extraer_campanas_tab(bloque, page, "Bonos y Descuen.")
                            campanas_extra.extend(bonos)
                            ct = _extraer_campanas_tab(bloque, page, "Cambio Tarifa")
                            campanas_extra.extend(ct)
                            sva = _extraer_campanas_tab(bloque, page, "SVA")
                            campanas_extra.extend(sva)
                            # === Dropdown "Otros" (3 puntitos) ===
                            try:
                                dropdown_btn = tab_bar_camp.locator("button.dropdown-toggle")
                                if dropdown_btn.count() > 0:
                                    dropdown_btn.first.click(force=True, timeout=3000)
                                    page.wait_for_timeout(150)
                                    # Click en "Otros" del menú desplegable
                                    otros_btn = page.locator("button.dropdown-item:has-text('Otros')")
                                    if otros_btn.count() > 0:
                                        otros_btn.first.click(force=True, timeout=3000)
                                        page.wait_for_timeout(200)
                                        # Extraer cards visibles (ahora bajo "Otros")
                                        cards_c = bloque.locator(".client-tariff-section-cards")
                                        if cards_c.count() > 0:
                                            cards = cards_c.locator(".card-tariff-minimal")
                                            for c_idx in range(cards.count()):
                                                card = cards.nth(c_idx)
                                                try:
                                                    lbl = card.locator(".card-tariff-label strong")
                                                    tipo2 = lbl.first.inner_text().strip() if lbl.count() > 0 else "Otros"
                                                    info2 = card.locator(".card-tariff-info-text")
                                                    txt2 = info2.first.inner_text().strip() if info2.count() > 0 else ""
                                                    if txt2:
                                                        campanas_extra.append({"tipo": tipo2, "texto": txt2})
                                                except Exception:
                                                    pass
                            except Exception:
                                pass
                            # Volver a Renove para no romper la iteración
                            try:
                                renove_back = tab_bar_camp.locator("button:has-text('Renove')")
                                if renove_back.count() > 0:
                                    renove_back.first.click(force=True, timeout=2000)
                                    page.wait_for_timeout(120)
                            except Exception:
                                pass
                    except Exception:
                        pass
                    # Campañas 'Otros' ya visibles sin hacer click adicional
                    otros = _extraer_campanas_otros(bloque)
                    campanas_extra.extend(otros)

                    # DEDUP: eliminar duplicados (mismo tipo + texto, case-insensitive)
                    seen = set()
                    campanas_extra = [c for c in campanas_extra if not (
                        f"{c.get('tipo','').lower()}|{c.get('texto','').lower()}" in seen 
                        or seen.add(f"{c.get('tipo','').lower()}|{c.get('texto','').lower()}")
                    )]

                    lineas_finales.append({
                        "DNI": dni,
                        "Nombre": nombre,
                        "Direccion": direccion,
                        "Seg Fijo": seg_fijo,
                        "Seg Movil": seg_movil,
                        "Paquete": paquete_tariff,
                        "Linea": num_linea,
                        "es_cima": es_cima,
                        "tiene_renove_mixto": tiene_rm,
                        "variante_renove": variante_renove,
                        "tiene_tv": tiene_tv,
                        "es_principal": es_principal,
                        "etiquetas": etiquetas,
                        "activo_desde": activo_desde,
                        # NUEVOS CAMPOS
                        "producto": producto_linea,
                        "estado_linea": estado_linea,
                        "permanencia": permanencia,
                        "permanencia_fecha": permanencia_fecha,
                        "consumo": consumo,
                        "venta_plazos": venta_plazos,
                        "campanas_extra": campanas_extra,
                        "notificacion_pack": notificacion_pack,
                    })

                # Siguiente página de líneas
                btn_siguiente = page.locator("button.ocs-pagination-next").first
                if (btn_siguiente.count() > 0
                        and not btn_siguiente.is_disabled()):
                    # Verificar si la PRIMERA línea de esta página ya se procesó (loop)
                    if pagina_actual > 1 and lineas_finales and num_linea in lineas_vistas:
                        print(f"  [Extracción] [!!] Loop detectado en página {pagina_actual}. Saliendo de paginacion.")
                        hay_mas_paginas = False
                    else:
                        print("  [Extracción] -> Siguiente página de líneas...")
                        btn_siguiente.click(force=True, timeout=30000)
                        page.wait_for_timeout(1000)
                        pagina_actual += 1
                else:
                    hay_mas_paginas = False

            return lineas_finales

        except Exception as e:
            print(f"  [Extracción] [WARN] Error recuperable: {e}")
            if intento < max_intentos - 1:
                print("  [Extracción] [RETRY] Recuperando sesión...")
                recuperado = False
                try:
                    page.reload(timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)

                    # ── Detect if we landed on the login page (session expired) ──
                    current_url = page.url
                    if "applogin.orange.es" in current_url or "/obrareq.cgi" in current_url:
                        print("  [Extracción] [LOGIN] Sesión expirada — re-logueando...")
                        try:
                            realizar_login(page)
                            seleccionar_marca_orange(page)
                            abrir_nuevo_acto_comercial(page)
                            print("  [Extracción] [OK] Re-login exitoso")
                            recuperado = True
                        except LoginError as le:
                            if "Maximo de sesiones" in str(le):
                                print("  [Extracción] [MAXSES] No hay sesiones — durmiendo 5 min")
                                time.sleep(300)
                            else:
                                print(f"  [Extracción] [LOGIN] Error en login: {le}")
                            recuperado = False
                        except Exception as ex:
                            print(f"  [Extracción] [LOGIN] Error inesperado: {ex}")
                            recuperado = False
                    else:
                        # ── F5 standard recovery (still on Pangea) ──
                        if page.locator("a.orange-box").is_visible(timeout=5000):
                            page.locator("a.orange-box").click()
                            page.wait_for_timeout(2000)
                        abrir_nuevo_acto_comercial(page)
                        print("  [Extracción] [OK] Sesión recuperada tras F5")
                        recuperado = True
                except Exception as ex:
                    print(f"  [Extracción] F5 falló: {ex}")
                if not recuperado:
                    print("  [Extracción] [FAIL] No se pudo recuperar")
            else:
                return []  # vacío -> worker marca error para reintentar


def verificar_sesion_valida(page: Page) -> bool:
    """Verifica si la sesión actual sigue siendo válida."""
    try:
        page.locator("button[title='Cambiar cliente']").wait_for(
            state="visible", timeout=5000
        )
        return True
    except Exception:
        return False
