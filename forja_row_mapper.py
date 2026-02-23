# forja_row_mapper.py
import re
import math
from datetime import datetime
import hashlib
from collections import defaultdict

from forja_headers import HEADERS_FORJA_INGESTA

# ==============================
# Índice maestro por nombre
# ==============================

COL_IDX = {h: i for i, h in enumerate(HEADERS_FORJA_INGESTA)}

# ==============================================================================
#  DEFINICIÓN DE ÍNDICES PARA VALIDACIÓN
# ==============================================================================
try:
    # Columnas a validar si están vacías
    IDX_DX = HEADERS_FORJA_INGESTA.index("DX codigo")
    IDX_NOMBRE = HEADERS_FORJA_INGESTA.index("Nombre de Medicamento")
    IDX_CANT = HEADERS_FORJA_INGESTA.index("Cantidad")
    IDX_POSOLOGIA = HEADERS_FORJA_INGESTA.index("Posología")
    IDX_DIAS = HEADERS_FORJA_INGESTA.index("TiempoDeTratamiento en dias")

    # Columna llave de agrupación
    IDX_ADMISION = HEADERS_FORJA_INGESTA.index("Admision")

    # Columna objetivo donde se escribirá el estado
    IDX_ESTADO_ORDEN = HEADERS_FORJA_INGESTA.index("ESTADO_ORDEN")

except ValueError as e:
    raise RuntimeError(f"[FORJA CRITICAL] Falta columna requerida para validación en HEADERS: {e}")


def _set_col(row, col_name, value):
    idx = COL_IDX.get(col_name)

    if idx is None:
        raise ValueError(f"[FORJA] Columna inexistente en INGESTA: {col_name}")

    row[idx] = "" if value is None else str(value)


def validar_campos_obligatorios_fila(fila: list) -> bool:
    """
    Revisa una fila individual. Devuelve True si FALTA algún dato obligatorio.
    """
    columnas_a_revisar = [IDX_DX, IDX_NOMBRE, IDX_CANT, IDX_POSOLOGIA, IDX_DIAS]

    for idx in columnas_a_revisar:
        valor = str(fila[idx]).strip()
        if not valor:
            return True # Faltan datos

    return False # La fila está completa


# ==============================
# Constructor principal FORJA
# ==============================

def construir_filas_forja(
    resultado_extractor: dict,
    *,
    archivo_origen: str,
    ruta_carpeta: str,
    link_pdf: str,
    link_correo: str,
):

    filas_crudas_temporales = []

    globales = resultado_extractor.get("globales", {})
  
    tipo_doc = globales.get("tipo_doc", "")
    documento = globales.get("documento", "")
    nit = globales.get("nit_empresa", "")
    contactos = ",".join(globales.get("contactos", []))
    fecha_cita = globales.get("fecha_cita", "")

    formulas = resultado_extractor.get("formulas", [])

    # -------------------------------------------------------
    # PASO 1: CONSTRUCCIÓN INICIAL DE FILAS
    # -------------------------------------------------------
    for idx_formula, formula in enumerate(formulas, start=1):

        formula_id = formula.get("formula_key", "")
        medicamentos = formula.get("medicamentos", [])

        for med in medicamentos:

            nombre_med = str(med.get("nombre_medicamento", "")).strip()

            # Corte clínico duro: sin nombre no existe medicamento
            if not nombre_med:
                continue

            cantidad = med.get("cantidad", "")
            posologia = med.get("posologia", "")
            dias = med.get("dias", "")
            dx = med.get("dx", "")
            alerta_logica = calcular_alerta_logica(
                nombre_med,
                cantidad,
                posologia,
                dias
            )

            # MEDICAMENTO_ID estable
            base_med = f"{formula_id}|{nombre_med}|{cantidad}|{posologia}"
            medicamento_id = hashlib.sha256(base_med.encode("utf-8")).hexdigest()[:16]

            # Crear fila alineada exacta
            fila = [""] * len(HEADERS_FORJA_INGESTA)

            # --------- MAPPING ---------

            _set_col(fila, "Tipo de Documento", tipo_doc)
            _set_col(fila, "N° de Documento", documento)
            _set_col(fila, "Nit Empresa", nit)
            _set_col(fila, "DX codigo", dx)

            _set_col(fila, "Nombre de Medicamento", nombre_med)
            _set_col(fila, "Cantidad", cantidad)
            _set_col(fila, "Posología", posologia)
            _set_col(fila, "TiempoDeTratamiento en dias", dias)

            _set_col(fila, "N° de contacto paciente", contactos)
            _set_col(fila, "Fecha de la cita AAAAMMDD", fecha_cita)

            _set_col(fila, "LINK_PDF", link_pdf)
            # _set_col(fila, "ARCHIVO_ORIGEN", archivo_origen)
            _set_col(fila, "RUTA_CARPETA", ruta_carpeta)
            _set_col(fila, "LINK_CORREO", link_correo)

            _set_col(
                fila,
                "FECHA_PROCESO",
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            _set_col(fila, "ALERTA_LOGICA", alerta_logica)

            _set_col(fila, "Admision", formula_id)

            # El estado se deja vacío inicialmente
            _set_col(fila, "ESTADO_ORDEN", "")

            # ---------- VALIDACIÓN ESTRUCTURAL ----------

            if len(fila) != len(HEADERS_FORJA_INGESTA):
                raise RuntimeError(
                    f"[FORJA] Fila desalineada: {len(fila)} != {len(HEADERS_FORJA_INGESTA)}"
                )

            filas_crudas_temporales.append(fila)

    # -------------------------------------------------------
    # PASO 2: POST-PROCESAMIENTO Y VALIDACIÓN GRUPAL
    # -------------------------------------------------------

    if not filas_crudas_temporales:
        return []

    formulas_agrupadas = defaultdict(list)
    for fila in filas_crudas_temporales:
        admision_key = fila[IDX_ADMISION]
        formulas_agrupadas[admision_key].append(fila)

    filas_finales_procesadas = []

    for admision_key, grupo_filas in formulas_agrupadas.items():

        formula_completa_tiene_error = False

        # Revisar si ALGUNA fila del grupo tiene campos vacíos
        for fila in grupo_filas:
            if validar_campos_obligatorios_fila(fila):
                formula_completa_tiene_error = True
                break

        estado_final_grupo = "🔴 FORMULA CON ERROR" if formula_completa_tiene_error else "✅ OK"

        # Colocar estado SOLO en la primera fila de la fórmula (para visualización limpia)
        for indice, fila in enumerate(grupo_filas):
            if indice == 0:
                fila[IDX_ESTADO_ORDEN] = estado_final_grupo
            else:
                fila[IDX_ESTADO_ORDEN] = ""
                
            filas_finales_procesadas.append(fila)

    return filas_finales_procesadas

import re
import math

FORMAS_VALIDABLES = [
    "tableta",
    "tabletas",
    "capsula",
    "capsulas",
    "sobre",
    "sobres",
    "ovulo",
    "ovulos",
    "parche",
    "parches"
]


def es_forma_validable(nombre):
    nombre = nombre.lower()
    return any(f in nombre for f in FORMAS_VALIDABLES)



import re

def extraer_dosis_por_dia(posologia: str):
    """
    Retorna la cantidad de unidades administradas por día.
    Si no es posible calcular con precisión, retorna None.
    """

    if not posologia:
        return None

    # ---------------------------
    # NORMALIZACIÓN
    # ---------------------------
    p = posologia.lower().strip()

    p = p.replace("horas", "h")
    p = p.replace("hrs", "h")
    p = p.replace("hr", "h")
    p = p.replace("cada día", "cada dia")
    p = p.replace("diaria", "cada dia")
    p = p.replace("diario", "cada dia")
    p = p.replace("diarios", "cada dia")

    # ---------------------------
    # FORMATO 1-1-2
    # ---------------------------
    match_tripleta = re.search(r"(\d+)\s*-\s*(\d+)\s*-\s*(\d+)", p)
    if match_tripleta:
        return sum(int(x) for x in match_tripleta.groups())

    # ---------------------------
    # "X veces al dia"
    # ---------------------------
    match_veces = re.search(r"(\d+)\s*veces\s*al\s*dia", p)
    if match_veces:
        return int(match_veces.group(1))

    # ---------------------------
    # "cada X h"
    # ---------------------------
    match_horas = re.search(r"cada\s+(\d+)\s*h", p)
    if match_horas:
        horas = int(match_horas.group(1))
        if horas > 0:
            return round(24 / horas, 2)

    # ---------------------------
    # cada dia / cada noche
    # ---------------------------
    if "cada dia" in p:
        return 1

    if "cada noche" in p:
        return 1

    if "cada 24h" in p:
        return 1

    # ---------------------------
    # MEDIA TABLETA
    # ---------------------------
    if "media tableta" in p or "medio tab" in p or "media tab" in p:
        # detectar frecuencia
        match_horas = re.search(r"cada\s+(\d+)\s*h", p)
        if match_horas:
            horas = int(match_horas.group(1))
            if horas > 0:
                return round((24 / horas) * 0.5, 2)

        if "cada dia" in p:
            return 0.5

    # ---------------------------
    # FORMATO "2 puff cada 8h"
    # ---------------------------
    match_puff = re.search(r"(\d+)\s*(tab|tableta|capsula|cap|puff|parche|sobre)", p)
    if match_puff:
        cantidad_por_toma = int(match_puff.group(1))

        match_horas = re.search(r"cada\s+(\d+)\s*h", p)
        if match_horas:
            horas = int(match_horas.group(1))
            if horas > 0:
                veces_dia = 24 / horas
                return round(cantidad_por_toma * veces_dia, 2)

        if "cada dia" in p:
            return cantidad_por_toma

    # ---------------------------
    # FORMATO SIMPLE "1 tableta cada 12h"
    # ---------------------------
    match_simple = re.search(r"(\d+)\s*(tab|tableta|capsula|cap)", p)
    if match_simple:
        cantidad_por_toma = int(match_simple.group(1))

        match_horas = re.search(r"cada\s+(\d+)\s*h", p)
        if match_horas:
            horas = int(match_horas.group(1))
            if horas > 0:
                veces_dia = 24 / horas
                return round(cantidad_por_toma * veces_dia, 2)

        if "cada dia" in p:
            return cantidad_por_toma

    # ---------------------------
    # NO SE PUEDE CALCULAR
    # ---------------------------
    return None

def extraer_unidades_por_toma(posologia):
    posologia = posologia.lower()

    match = re.search(r"(\d+)\s*(tab|tableta|capsula|sobre|parche)", posologia)
    if match:
        return int(match.group(1))

    if "media" in posologia:
        return 0.5

    return 1


def calcular_alerta_logica(nombre, cantidad, posologia, dias):

    try:
        cantidad = float(cantidad)
        dias = float(dias)
    except:
        return "⚪ NO SE PUEDE VALIDAR"

    if cantidad <= 0 or dias <= 0:
        return "⚪ NO SE PUEDE VALIDAR"

    if not es_forma_validable(nombre):
        return "⚪ NO SE PUEDE VALIDAR"

    dosis_por_dia = extraer_dosis_por_dia(posologia)
    if dosis_por_dia is None:
        return "⚪ NO SE PUEDE VALIDAR"

    unidades_por_toma = extraer_unidades_por_toma(posologia)

    esperado = dosis_por_dia * unidades_por_toma * dias
    esperado = round(esperado)

    if abs(esperado - cantidad) < 0.01:
        return "✅ OK"

    if cantidad < esperado:
        return "🟠 FALTA CANTIDAD"

    if cantidad > esperado:
        return "🔴 SOBRA CANTIDAD"

    return "⚪ NO SE PUEDE VALIDAR"