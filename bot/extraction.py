"""
extraction.py — Extraccion de datos de cliente en Pangea Orange
=================================================================
Version reescrita. Flujo modular: buscar → detectar → cabecera → lineas.

Casuisticas: PYME, GGCC, MAX LINEAS, NO ES CLIENTE, frozen, ERROR CAMPANAS.
"""

import random
import re
import time
from playwright.sync_api import Page

# ── Re-export desde login.py ─────────────────────
from login import (
    _escribir_como_humano,
    _extraer_texto,
    _extraer_estado_linea,
    _extraer_detalle_linea,
    _extraer_campanas_tab,
    _extraer_campanas_otros,
    _detectar_no_cliente_explicito,
    _hay_toast_error,
    _abrir_cambiar_cliente,
    _blindar_contra_tools_dropdown,
    _verificar_no_navego_fuera,
    _reset_frozen,
    _increment_frozen,
    _FROZEN_LIMIT,
    parsear_fecha_permanencia,
    PangeaDownError,
)


# ── Helpers ──────────────────────────────────────

def _fila_vacia(dni, nombre="N/A", modal_abierto=False):
    """Template de fila de resultado con todos los campos."""
    return {
        "DNI": dni, "Nombre": nombre, "Direccion": "N/A",
        "Seg Fijo": "N/A", "Seg Movil": "N/A", "Paquete": "N/A",
        "Linea": dni, "es_cima": False, "tiene_renove_mixto": False,
        "variante_renove": "N/A", "tiene_tv": False, "es_principal": False,
        "etiquetas": [], "activo_desde": "N/A", "producto": "N/A",
        "estado_linea": [], "permanencia": "N/A", "consumo": "N/A",
        "venta_plazos": "N/A", "campanas_extra": [], "_modal_abierto": modal_abierto,
    }


def _cerrar_modal_error(page):
    """Intenta cerrar el modal de error (PYME, GGCC, etc)."""
    try:
        btn = page.locator("button.close[data-dismiss='modal']").last
        if btn.count() > 0:
            btn.click(force=True, timeout=3000)
            page.wait_for_timeout(500)
    except Exception:
        pass


# ── FASE 1: Buscar cliente ──────────────────────

def _abrir_modal_busqueda(page, modal_ya_abierto=False):
    """Abre el modal de busqueda si no esta ya abierto."""
    if modal_ya_abierto:
        sel = "input[name='document']"
        try:
            page.wait_for_selector(sel, state="visible", timeout=5000)
        except Exception:
            page.wait_for_selector("input[ng-model='locatorCtrl.inputDocument']",
                                   state="visible", timeout=5000)
        return

    btn = page.locator("button[title='Cambiar cliente']")
    btn.wait_for(state="visible", timeout=15000)
    btn.click(force=True)
    page.wait_for_selector("input[name='document']", state="visible", timeout=10000)


def _escribir_numero(page, numero, es_telefono):
    """Escribe DNI o telefono en el campo correcto del modal."""
    if es_telefono:
        campo = page.locator("input[ng-model='locatorCtrl.inputMsisdn']").first
        campo.wait_for(state="visible", timeout=5000)
        campo.click()
        campo.fill("")
        campo.fill(numero.replace(' ', '').replace('-', ''))
    else:
        try:
            page.wait_for_selector("input[name='document']", state="visible", timeout=3000)
            sel = "input[name='document']"
        except Exception:
            sel = "input[ng-model='locatorCtrl.inputDocument']"
        campo = page.locator(sel).first
        campo.click()
        campo.fill("")
        campo.fill(numero)
    campo.evaluate(
        "el => { el.dispatchEvent(new Event('input', { bubbles: true })); "
        "el.dispatchEvent(new Event('change', { bubbles: true })); }"
    )


def _click_buscar(page, numero):
    """Click en 'Buscar cliente' + blindajes."""
    page.wait_for_timeout(random.randint(300, 800))
    btn = page.locator("button:has-text('Buscar cliente')").last
    btn.click(force=True)

    if not _verificar_no_navego_fuera(page, dni_actual=numero):
        print(f"  [!!] Navegacion externa tras click Buscar -- abortando {numero}")
        return False, btn

    try:
        btn.wait_for(state="hidden", timeout=5000)
    except Exception:
        pass

    if not _verificar_no_navego_fuera(page, dni_actual=numero):
        print(f"  [!!] Navegacion externa tras procesar {numero}")
        return False, btn

    return True, btn


# ── FASE 2: Deteccion temprana ──────────────────

_CASOS_ERROR = {
    "PYME": ("Cliente PYME", "CLIENTE PYME"),
    "GGCC": ("Cliente GGCC", "CLIENTE GGCC"),
    "MAX_LINEAS": ("supera el maximo de lineas permitidas", "CLIENTE MAX LINEAS"),
}


def _detectar_caso_error(page, numero):
    """Detecta PYME, GGCC o MAX LINEAS en el modal de error.
    Retorna (Nombre, fila) o (None, None)."""
    for tag, (selector_text, nombre_fila) in _CASOS_ERROR.items():
        try:
            matches = page.locator(f".msg-error:has-text('{selector_text}')")
            for j in range(matches.count()):
                if matches.nth(j).is_visible():
                    print(f"  [{tag}] {numero} -> {nombre_fila}")
                    _cerrar_modal_error(page)
                    fila = _fila_vacia(numero, nombre=nombre_fila)
                    return nombre_fila, fila
        except Exception:
            pass
    return None, None


def _detectar_no_cliente(page, numero, es_telefono):
    """Detecta NO ES CLIENTE explicito. Retorna fila o None."""
    if _detectar_no_cliente_explicito(page, es_telefono):
        _reset_frozen()
        print(f"  [FAIL] {numero} NO ES CLIENTE")
        fila = _fila_vacia(numero, nombre="NO ES CLIENTE", modal_abierto=True)
        return fila
    return None


def _detectar_frozen(page, numero, btn_buscar):
    """Detecta Pangea congelada (modal abierto sin texto de error).
    Retorna (fila, detener) o (None, False)."""
    try:
        if btn_buscar.is_visible():
            if _increment_frozen():
                print(f"  [!!] {_FROZEN_LIMIT} DNIs sin respuesta. F5...")
                _reset_frozen()
                page.reload(timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                if "pangea.orange.es" not in page.url:
                    raise Exception("Pangea no disponible tras F5")
                print("  Pangea respondio. Reabriendo modal...")
                try:
                    btn = page.locator("button[title='Cambiar cliente']")
                    btn.wait_for(state="visible", timeout=10000)
                    btn.click(force=True)
                    page.wait_for_selector("input[name='document']", state="visible", timeout=10000)
                except Exception:
                    pass
            print(f"  [WARN] {numero}: Pangea congelada")
            return [], False
    except Exception:
        pass
    return None, False


def _detectar_toast_error(page, numero):
    """Detecta toast 'No se han podido recuperar campanas'.
    Retorna fila o None."""
    if _hay_toast_error(page):
        print(f"  [FAIL] {numero}: error campanas (temprano)")
        _abrir_cambiar_cliente(page)
        return _fila_vacia(numero, nombre="ERROR CAMPANAS", modal_abierto=True)
    return None


# ── FASE 3: Cabecera ────────────────────────────

def _extraer_cabecera(page, numero, es_telefono):
    """Extrae datos de cabecera del cliente. Retorna dict o lanza excepcion."""
    print("  Cargando ficha de cliente...")
    page.wait_for_timeout(1500)
    page.wait_for_selector(".mod-barclient__container-data", timeout=20000)

    # CIMA global
    cima_global = False
    try:
        btn = page.locator(".mod-barclient__container-lines-cima-btn")
        if btn.count() > 0:
            txt = btn.first.inner_text()
            cima_global = "isCima" in txt or "CIMA" in txt.upper()
    except Exception:
        pass

    nombre = _extraer_texto(page, ".tooltip-text.name strong")
    dni = _extraer_texto(page, "span.font-xxs.p-r-10")

    # Validar DNI coincide (solo busqueda por DNI)
    dni_limpio = dni.strip().upper().replace("-", "").replace(".", "").replace(" ", "")
    buscado_limpio = numero.strip().upper().replace("-", "").replace(".", "").replace(" ", "")
    if not es_telefono and dni_limpio and dni_limpio not in ("N/A", "") and dni_limpio != buscado_limpio:
        raise Exception(f"DNI mismatch: buscado {numero} != pagina {dni}")

    # Skip duplicados (busqueda por telefono)
    if es_telefono and dni_limpio and dni_limpio not in ("N/A", ""):
        try:
            import requests, os as _os
            from pathlib import Path as _Path
            from dotenv import load_dotenv as _ld
            _ld(_Path(__file__).parent.parent / '.env')
            r = requests.get(
                f"{_os.getenv('BOT_API_URL', 'http://localhost:3000')}/api/clientes/{dni_limpio}",
                headers={"x-bot-api-key": _os.getenv('BOT_API_KEY', 'oratioo-bot-internal-key')},
                timeout=5,
            )
            if r.ok and r.json():
                print(f"  [SKIP] Cliente {dni_limpio} ya procesado")
                f = _fila_vacia(dni_limpio, nombre="YA_PROCESADO")
                f["_skip"] = True
                f["Linea"] = numero
                return None, f  # señal: skip
        except Exception:
            pass

    direccion = _extraer_texto(page, ".tooltip-text.address")
    seg_fijo = _extraer_texto(page, "div.font-xxs:has-text('Seg. Fijo:') strong")
    seg_movil = _extraer_texto(page, "div.font-xxs:has-text('Seg. Móvil:') strong")
    paquete = _extraer_texto(page, ".client-tariff-title .font-lg")

    # Notificacion pack
    notificacion_pack = ""
    try:
        el = page.locator(".notification-container .message-relevant.info p.title")
        if el.count() > 0:
            notificacion_pack = el.first.inner_text().strip()
    except Exception:
        pass

    print(f"  Cliente: {nombre} | DNI: {dni} | Paquete: {paquete}")
    return {
        "dni": dni, "nombre": nombre, "direccion": direccion,
        "seg_fijo": seg_fijo, "seg_movil": seg_movil, "paquete": paquete,
        "cima_global": cima_global, "notificacion_pack": notificacion_pack,
        "dni_limpio": dni_limpio,
    }, None


def _detectar_toast_tardio(page, numero):
    """Toast error despues de extraer cabecera."""
    if _hay_toast_error(page):
        print(f"  [FAIL] {numero}: error campanas (tardio)")
        _abrir_cambiar_cliente(page)
        return _fila_vacia(numero, nombre="ERROR CAMPANAS", modal_abierto=True)
    return None


# ── FASE 4: Lineas ──────────────────────────────

def _extraer_renove(bloque, page):
    """Extrae datos de Renove de una linea. Retorna (tiene_rm, variante, texto_raw)."""
    tiene_rm = False
    variante = "N/A"
    texto_raw = ""

    # Verificar heading
    heading_text = ""
    tiene_rm_heading = False
    try:
        heading_text = bloque.locator(".client-tariff-heading").first.inner_text()
        tiene_rm_heading = bool(re.search(r'\b(Renove|MIXTO)\b', heading_text, re.IGNORECASE))
    except Exception:
        pass

    try:
        tab_bar = bloque.locator(".client-tariff-section-navs")
        if tab_bar.count() == 0:
            if tiene_rm_heading:
                return True, "Renove (detectado en heading)", heading_text[:80]
            return False, "N/A", ""

        renove_tab = tab_bar.locator("button:has-text('Renove')")
        if renove_tab.count() == 0:
            if tiene_rm_heading:
                return True, "Renove (detectado en heading)", heading_text[:80]
            return False, "N/A", ""

        # Click en tab Renove
        try:
            renove_tab.first.click(timeout=5000)
        except Exception:
            renove_tab.first.click(force=True, timeout=5000)
        page.wait_for_timeout(500)

        # Leer card
        texto_card = ""
        cards_cont = bloque.locator(".client-tariff-section-cards")
        if cards_cont.count() > 0:
            cards = cards_cont.locator(".card-tariff-minimal")
            for c in range(cards.count()):
                card = cards.nth(c)
                txt_el = card.locator(".card-tariff-info-text")
                txt = txt_el.first.inner_text().strip() if txt_el.count() > 0 else card.inner_text().strip()
                if re.search(r'\b(RENOVE|MIXTO|MULTIDISPOSITIVO)\b', txt.upper()):
                    texto_card = txt
                    break
                if not texto_card:
                    texto_card = txt

        up = texto_card.upper() if texto_card else ""
        tiene_rm = bool(texto_card and re.search(r'\b(RENOVE|MIXTO|MULTIDISPOSITIVO)\b', up))

        if "MIXTO" in up:
            if "MAXIMO DESCUENTO" in up or "MÁXIMO DESCUENTO" in up:
                variante = "Renove mixto al mejor precio con maximo descuento"
            elif "CON DESCUENTO" in up:
                variante = "Renove mixto al mejor precio con descuento"
            elif "MEJOR PRECIO" in up:
                variante = "Renove mixto al mejor precio"
            else:
                variante = "Renove mixto"
        elif "MULTIDISPOSITIVO" in up:
            variante = "Renove Multidispositivo"
        elif texto_card:
            variante = f"Renove ({texto_card})"

        texto_raw = texto_card.strip() if texto_card else variante
        print(f"      [RENOVE] {texto_card[:80] if texto_card else '(vacio)'} -> {variante}")
    except Exception as e:
        print(f"      [RENOVE] Error: {e}")

    if not tiene_rm and tiene_rm_heading:
        return True, "Renove (detectado en heading)", heading_text[:80]

    return tiene_rm, variante, texto_raw


def _extraer_campanas(bloque, page, tiene_rm, renove_raw, variante_renove):
    """Extrae todas las campanas de una linea."""
    campanas = []
    if tiene_rm and (renove_raw or variante_renove not in ("N/A", "")):
        campanas.append({"tipo": "Renove", "texto": renove_raw or variante_renove})

    try:
        tab_bar = bloque.locator(".client-tariff-section-navs")
        if tab_bar.count() > 0:
            for tab in ["Bonos y Descuen.", "Cambio Tarifa", "SVA"]:
                campanas.extend(_extraer_campanas_tab(bloque, page, tab))

            # Dropdown Otros
            try:
                dd = tab_bar.locator("button.dropdown-toggle")
                if dd.count() > 0:
                    dd.first.click(force=True, timeout=3000)
                    page.wait_for_timeout(400)
                    otros_btn = page.locator("button.dropdown-item:has-text('Otros')")
                    if otros_btn.count() > 0:
                        otros_btn.first.click(force=True, timeout=3000)
                        page.wait_for_timeout(500)
                        cards_c = bloque.locator(".client-tariff-section-cards")
                        if cards_c.count() > 0:
                            for card in cards_c.locator(".card-tariff-minimal").all():
                                try:
                                    lbl = card.locator(".card-tariff-label strong")
                                    tipo = lbl.first.inner_text().strip() if lbl.count() > 0 else "Otros"
                                    info = card.locator(".card-tariff-info-text")
                                    txt = info.first.inner_text().strip() if info.count() > 0 else ""
                                    if txt:
                                        campanas.append({"tipo": tipo, "texto": txt})
                                except Exception:
                                    pass
            except Exception:
                pass

            # Volver a Renove
            try:
                back = tab_bar.locator("button:has-text('Renove')")
                if back.count() > 0:
                    back.first.click(force=True, timeout=2000)
                    page.wait_for_timeout(200)
            except Exception:
                pass
    except Exception:
        pass

    campanas.extend(_extraer_campanas_otros(bloque))

    # DEDUP
    seen = set()
    return [c for c in campanas if not (
        f"{c.get('tipo','').lower()}|{c.get('texto','').lower()}" in seen
        or seen.add(f"{c.get('tipo','').lower()}|{c.get('texto','').lower()}")
    )]


def _procesar_linea(bloque, page, cabecera, lineas_vistas):
    """Procesa un bloque .client-tariff-flex (una linea del cliente).
    Retorna dict con datos de la linea."""
    # Numero de linea
    num_linea = bloque.locator(".line-section .color-primary strong").inner_text().strip()
    if num_linea in lineas_vistas:
        return None  # loop detectado
    lineas_vistas.add(num_linea)

    # Paquete del tariff
    paquete_tariff = cabecera["paquete"]
    try:
        parent = bloque.locator(
            "xpath=ancestor::div[contains(concat(' ', normalize-space(@class), ' '), ' client-tariff ')]")
        if parent.count() > 0:
            for sel in [".client-tariff-title .font-lg", ".font-lg", "h2, h3, [class*='title']"]:
                el = parent.first.locator(sel)
                if el.count() > 0:
                    paquete_tariff = el.first.inner_text().strip()
                    break
    except Exception:
        pass

    print(f"    -> Linea: {num_linea} | Tariff: {paquete_tariff}")

    # Etiquetas
    etiquetas = []
    texto_completo = ""
    try:
        heading = bloque.locator(".client-tariff-heading")
        etiquetas = [heading.locator("span.label").nth(k).inner_text().strip()
                     for k in range(heading.locator("span.label").count())]
        texto_completo = heading.first.inner_text()
    except Exception:
        pass

    es_cima = "CIMA" in etiquetas or cabecera["cima_global"]
    tiene_tv = "TV" in etiquetas
    es_principal = "Principal" in etiquetas
    m = re.search(r'Activo desde\s+(\d{2}/\d{2}/\d{4})', texto_completo)
    activo_desde = m.group(1) if m else "N/A"

    # Producto
    producto_linea = "N/A"
    try:
        strongs = bloque.locator(".line-section strong")
        if strongs.count() >= 2:
            producto_linea = strongs.nth(1).inner_text().strip()
    except Exception:
        pass

    # Estado, permanencia, consumo, VAP
    estado_linea = _extraer_estado_linea(bloque)
    permanencia = _extraer_detalle_linea(bloque, "Permanencia")
    permanencia_fecha = parsear_fecha_permanencia(permanencia)
    consumo = _extraer_detalle_linea(bloque, "Consumo")
    venta_plazos = _extraer_detalle_linea(bloque, "Venta a Plazos")

    # Renove
    tiene_rm, variante_renove, renove_raw = _extraer_renove(bloque, page)

    # Campanas
    campanas_extra = _extraer_campanas(bloque, page, tiene_rm, renove_raw, variante_renove)

    return {
        "DNI": cabecera["dni"],
        "Nombre": cabecera["nombre"],
        "Direccion": cabecera["direccion"],
        "Seg Fijo": cabecera["seg_fijo"],
        "Seg Movil": cabecera["seg_movil"],
        "Paquete": paquete_tariff,
        "Linea": num_linea,
        "es_cima": es_cima,
        "tiene_renove_mixto": tiene_rm,
        "variante_renove": variante_renove,
        "tiene_tv": tiene_tv,
        "es_principal": es_principal,
        "etiquetas": etiquetas,
        "activo_desde": activo_desde,
        "producto": producto_linea,
        "estado_linea": estado_linea,
        "permanencia": permanencia,
        "permanencia_fecha": permanencia_fecha,
        "consumo": consumo,
        "venta_plazos": venta_plazos,
        "campanas_extra": campanas_extra,
        "notificacion_pack": cabecera["notificacion_pack"],
    }


def _extraer_lineas(page, cabecera):
    """Bucle de paginacion de lineas. Retorna lista de dicts."""
    lineas = []
    vistas = set()
    pagina = 1

    while True:
        print(f"  Pagina {pagina} de lineas...")
        bloques = page.locator(".client-tariff-flex")

        for i in range(bloques.count()):
            bloque = bloques.nth(i)
            if not bloque.locator(".line-section .color-primary strong").is_visible():
                continue

            fila = _procesar_linea(bloque, page, cabecera, vistas)
            if fila is None:
                print("    [!!] Loop de paginacion detectado. Saliendo.")
                return lineas
            lineas.append(fila)

        # Siguiente pagina
        btn = page.locator("button.ocs-pagination-next").first
        if btn.count() == 0 or btn.is_disabled():
            break
        btn.click(force=True, timeout=30000)
        page.wait_for_timeout(2000)
        pagina += 1

    return lineas


# ── FASE 5: Orquestador ─────────────────────────

def extraer_datos_cliente(page: Page, numero: str, buscar_por_dni: bool = True,
                           modal_ya_abierto: bool = False):
    """Busca cliente y extrae todos sus datos. Retorna lista de dicts (1 por linea)."""
    es_telefono = (numero.replace(' ', '').replace('-', '').isdigit()
                   and len(numero.replace(' ', '').replace('-', '')) == 9)
    max_intentos = 2

    for intento in range(max_intentos):
        print(f"  Buscando: {numero} (Intento {intento+1}) {'[TEL]' if es_telefono else '[DNI]'}")
        try:
            # Blindaje 0
            if not _verificar_no_navego_fuera(page, dni_actual=numero):
                return []

            _blindar_contra_tools_dropdown(page)

            # FASE 1: Busqueda
            _abrir_modal_busqueda(page, modal_ya_abierto)
            _escribir_numero(page, numero, es_telefono)
            ok, btn_buscar = _click_buscar(page, numero)
            if not ok:
                return []

            # FASE 2: Deteccion temprana
            # 2.1 PYME / GGCC / MAX LINEAS
            _nombre_err, fila_err = _detectar_caso_error(page, numero)
            if fila_err:
                return [fila_err]

            # 2.2 NO ES CLIENTE
            fila_nc = _detectar_no_cliente(page, numero, es_telefono)
            if fila_nc:
                return [fila_nc]

            # 2.3 Frozen
            fila_frozen, _ = _detectar_frozen(page, numero, btn_buscar)
            if fila_frozen is not None:
                return fila_frozen  # [] -> frozen, reintentar

            # 2.4 Toast error temprano
            fila_toast = _detectar_toast_error(page, numero)
            if fila_toast:
                return [fila_toast]

            # FASE 3: Cabecera
            cabecera, skip = _extraer_cabecera(page, numero, es_telefono)
            if skip:
                return [skip]

            # Toast tardio
            toast = _detectar_toast_tardio(page, numero)
            if toast:
                return [toast]

            # FASE 4: Lineas
            lineas = _extraer_lineas(page, cabecera)
            if lineas:
                return lineas

            # Sin lineas -> retry
            print(f"  [WARN] Sin lineas extraidas. Reintentando...")
            if intento < max_intentos - 1:
                page.reload(timeout=30000, wait_until="domcontentloaded")
                page.wait_for_timeout(3000)
                if page.locator("a.orange-box").is_visible(timeout=5000):
                    page.locator("a.orange-box").click()
                    page.wait_for_timeout(2000)
                from login import abrir_nuevo_acto_comercial
                abrir_nuevo_acto_comercial(page)

        except Exception as e:
            print(f"  [WARN] Error: {e}")
            if intento < max_intentos - 1:
                print("  [RETRY] Recuperando sesion (F5)...")
                try:
                    page.reload(timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(3000)
                    if page.locator("a.orange-box").is_visible(timeout=5000):
                        page.locator("a.orange-box").click()
                        page.wait_for_timeout(2000)
                    from login import abrir_nuevo_acto_comercial
                    abrir_nuevo_acto_comercial(page)
                except Exception:
                    pass

    return []
