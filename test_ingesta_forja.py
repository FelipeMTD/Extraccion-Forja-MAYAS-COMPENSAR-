# test_ingesta_forja.py (versión estable + ahorro de cuota)

from datetime import datetime
import tempfile
import json
import os
import re
import sys
from collections import defaultdict
from forja_headers import HEADERS_FORJA_INGESTA as HEADERS_FORJA
from auth import obtener_servicios
from gmail_reader import buscar_mensajes, obtener_adjuntos
from zip_handler import extraer_pdfs
from date_picker import seleccionar_rango_fechas
from drive_storage import guardar_pdf_en_drive
# -- MODIFICADO: Agregamos fusionar_celdas_estado --
from sheets_writer import asegurar_headers, append_filas, fusionar_celdas_estado
from forja_row_mapper import construir_filas_forja
from forja_extraccion_pdfs import procesar_pdf
from gmail_labels import obtener_o_crear_label, aplicar_etiqueta
from forja_month_expander import  expandir_y_agrupar_por_hoja_mensual

EMAIL_FORJA = "juanfelipediazsantos@gmail.com"
ROOT_FORJA_ID = "1Ifweg7snLCZm3F_WDjG-5kSjM-2E49BD"
SPREADSHEET_ID_FORJA = "1W-gkbZ_hJ3AuTfqA-ZA8YwCMv4Uo5XYGtdEgm6l-ogc"  
#1FI-j8Jt1Ivo9gDEFKz9knv-7WSuqCxj-09zJ3HPW-tk
#1rinNBID2QcM_Sbqj_5jVUMlUcEpliHrX5lxnZ_tmd9Y
# SHEET_NAME_FORJA = "FORJA"

# EMAIL_FORJA = ["coordinacioncalidad@forjaempresas.com","auxiliardecalidad@forjaempresas.com"]
# ROOT_FORJA_ID = "1_WyddMMyfKi43MEOC_JRT0k23ra8usP6"
# SPREADSHEET_ID_FORJA = "1yuemQ9OQjDLm7xUjPPxn0QTrVumiXbTwtFST2mQhT8U" # NUEVO SOLO FORJAS POR MES PRODUCCION 
#  1YHI9qbRqGRgA0emwNke4ISqCb-oXEX4WeCTupJz53SE

SHEET_BASE_GENERAL = "BASE_GENERAL_FORJA"


def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))
BASE_DIR = get_base_path()
json_path = os.path.join(BASE_DIR, "Forja1.json")

with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)


def limpiar_fecha_cita(valor):
    if not valor:
        return None

    s = str(valor).strip()

    # AAAAMMDD
    if re.fullmatch(r"\d{8}", s):
        return s

    # YYYY-MM-DD
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return s.replace("-", "")

    return None


HEADERS_BASE_GENERAL = HEADERS_FORJA
HEADERS_MENSUAL = HEADERS_FORJA
          # con MES_ASIGNADO

MESES = {
    "01": "Enero", "02": "Febrero", "03": "Marzo",
    "04": "Abril", "05": "Mayo", "06": "Junio",
    "07": "Julio", "08": "Agosto", "09": "Septiembre",
    "10": "Octubre", "11": "Noviembre", "12": "Diciembre"
}


def _col_letter(n: int) -> str:
    """
    Convierte 1-based index a letra Excel/Sheets:
    1->A, 2->B, ... 26->Z, 27->AA, etc.
    """
    s = ""
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# def leer_ids_medicamento_existentes(sheets, spreadsheet_id, sheet_name, headers) -> set[str]:
#     """
#     Lee la columna REAL de MEDICAMENTO_ID según el header.
#     Dedup estable y a prueba de cambios de orden.
#     """
#     idx = headers.index("MEDICAMENTO_ID") + 1  # 1-based
#     col = _col_letter(idx)

#     resp = sheets.spreadsheets().values().get(
#         spreadsheetId=spreadsheet_id,
#         range=f"{sheet_name}!{col}2:{col}"
#     ).execute()

#     vals = resp.get("values", [])
#     return {row[0].strip() for row in vals if row and row[0].strip()}


if __name__ == "__main__":

    gmail, drive, sheets = obtener_servicios()

    # Cache de hojas existentes (se actualiza cuando creemos nuevas)
    ss = sheets.spreadsheets().get(spreadsheetId=SPREADSHEET_ID_FORJA).execute()
    HOJAS_EXISTENTES = {s["properties"]["title"] for s in ss.get("sheets", [])}

    LABEL_FORJA_ID = obtener_o_crear_label(gmail, "FORJA")

    fecha_inicio, fecha_fin = seleccionar_rango_fechas()

    print(f"[FORJA] Buscando correos desde {fecha_inicio.date()} hasta {fecha_fin.date()}")

    mensajes = buscar_mensajes(
        gmail,
        EMAIL_FORJA,
        fecha_inicio,
        fecha_fin,
        "FORJA"
    )

    print(f"[FORJA] Correos encontrados: {len(mensajes)}")

    # 1) Asegurar BASE_GENERAL_FORJA una sola vez
    asegurar_headers(
        sheets,
        SPREADSHEET_ID_FORJA,
        SHEET_BASE_GENERAL,
        HEADERS_BASE_GENERAL,
        HOJAS_EXISTENTES,
    )
    HOJAS_EXISTENTES.add(SHEET_BASE_GENERAL)
    # existing_ids = set()
    # ===== CARGAR ADMISIONES EXISTENTES DESDE SHEETS =====

    idx_formula = HEADERS_FORJA.index("Admision") + 1
    col_letter = _col_letter(idx_formula)

    resp = sheets.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID_FORJA,
        range=f"{SHEET_BASE_GENERAL}!{col_letter}2:{col_letter}"
    ).execute()

    vals = resp.get("values", [])

    # existing_ids = {
    #     (row[0],)  # solo Admision
    #     for row in vals
    #     if row and row[0]
    # }
    existing_ids = {
        row[0].strip()
        for row in vals
        if row and row[0]
    }

    print(f"[INFO] Admision históricas cargadas: {len(existing_ids)}")


    # Acumuladores globales (batch real)
    todas_filas_nuevas_base_general = []              # filas sin MES (17 cols)
    por_hoja_mensual = defaultdict(list)              # hoja mensual -> filas con MES (18 cols)

    # Control de etiquetado: solo etiquetar si TODO lo del correo fue OK
    correos_a_etiquetar = set()

    for m in mensajes:


        pdfs_ok = 0

        print(f"\n[FORJA] Correo ID: {m['id']}")

        try:
            adjuntos = obtener_adjuntos(gmail, m["id"])
            print(f"  Adjuntos: {[a[0] for a in adjuntos]}")

            if not adjuntos:
                print("  ⚠ Correo sin adjuntos")
                continue

            if "internalDate" in m:
                fecha_guardado = datetime.fromtimestamp(int(m["internalDate"]) / 1000)
            else:
                print("  ⚠ Correo sin internalDate, usando fecha actual")
                fecha_guardado = datetime.now()

            for nombre, data in adjuntos:

                pdfs = extraer_pdfs(data, nombre)
                print(f"    → PDFs desde {nombre}: {[p[0] if isinstance(p, (list, tuple)) else p for p in pdfs]}")

                if not pdfs:
                    continue

                for item in pdfs:

                    if not isinstance(item, (list, tuple)) or len(item) != 2:
                        print(f"      ✖ PDF inválido (estructura): {item}")
                        continue

                    nombre_pdf, data_pdf = item

                    filas_nuevas_pdf = []   # ← INICIALIZAR SIEMPRE POR PDF

                    tmp_path = None

                    try:
                        r = guardar_pdf_en_drive(
                            drive,
                            ROOT_FORJA_ID,
                            nombre_pdf,
                            data_pdf,
                            fecha_guardado
                        )

                        link_pdf = r["webViewLink"]
                        print(f"      ✔ Subido a Drive: {link_pdf}")

                        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                            tmp.write(data_pdf)
                            tmp_path = tmp.name

                        resultado = procesar_pdf(tmp_path, link_pdf)

                        meds_por_formula = [
                            len(f.get("medicamentos", []))
                            for f in resultado.get("formulas", [])
                        ]

                        total_meds = sum(meds_por_formula)

                        print(
                            f"      AUDITORÍA [{nombre_pdf}] → "
                            f"formulas={len(meds_por_formula)} | meds_por_formula={meds_por_formula}"
                        )
                     

                        if total_meds == 0:
                            print("      ⚠ PDF sin medicamentos")
                            continue

                        filas = construir_filas_forja(
                            resultado,
                            archivo_origen=nombre_pdf,
                            ruta_carpeta=f"/FORJA/{fecha_guardado.strftime('%Y-%m')}/{fecha_guardado.strftime('%Y-%m-%d')}",
                            link_pdf=link_pdf,
                            link_correo=f"https://mail.google.com/mail/u/0/#inbox/{m['id']}",
                        )
                        if not filas:
                            print("      ⚠ construir_filas_forja devolvió 0 filas")
                            continue

                        idx_formula = HEADERS_FORJA.index("Admision")
                        formula_id = filas[0][idx_formula]

                        if formula_id in existing_ids:
                            print("      ⚠ Fórmula ya existente → PDF completo descartado")
                            continue

                        existing_ids.add(formula_id)



                        filas_nuevas_pdf = []

                        for fila in filas:

                            # ---- VALIDACIÓN ESTRUCTURAL ----

                            if len(fila) != len(HEADERS_FORJA):
                                print("      ✖ Fila descartada (longitud inválida)")
                                continue


                            # ============================
                            # DEDUPE CLÍNICO REAL
                            # ============================

                            idx_doc = HEADERS_FORJA.index("N° de Documento")
                            idx_fecha = HEADERS_FORJA.index("Fecha de la cita AAAAMMDD")
                            idx_nombre = HEADERS_FORJA.index("Nombre de Medicamento")
                            idx_cantidad = HEADERS_FORJA.index("Cantidad")
                            idx_posologia = HEADERS_FORJA.index("Posología")

                            
                            

                            # clave_dedupe = (
                            #     fila[idx_doc].strip(),
                            #     fila[idx_fecha].strip(),
                            #     fila[idx_nombre].strip().upper(),
                            #     fila[idx_cantidad].strip(),
                            #     fila[idx_posologia].strip().upper(),
                            # )

                           

                            filas_nuevas_pdf.append(fila)

                            print("      ✔ ACEPTADO PARA INSERCION")

                        if not filas_nuevas_pdf:
                            print("      ℹ Todo duplicado vs BASE_GENERAL_FORJA")
                            continue

                        todas_filas_nuevas_base_general.extend(filas_nuevas_pdf)

                        pdfs_ok += 1   # <<< CLAVE

                        filas_nuevas_pdf = [
                            f for f in filas_nuevas_pdf
                            if str(f[HEADERS_FORJA.index("Fecha de la cita AAAAMMDD")]).isdigit()
                        ]

                        # ---------- FILTRO DE FECHAS VALIDAS (ANTES DE EXPANDIR) ----------

                        idx_fecha = HEADERS_FORJA.index("Fecha de la cita AAAAMMDD")

                        filas_nuevas_pdf = [
                            f for f in filas_nuevas_pdf
                            if str(f[idx_fecha]).isdigit() and len(str(f[idx_fecha])) == 8
                        ]

                        if not filas_nuevas_pdf:
                            print("      ⚠ PDF sin filas válidas con fecha")
                            continue

                        grupos = expandir_y_agrupar_por_hoja_mensual(filas_nuevas_pdf)
                        for hoja, filas_mes in grupos.items():
                            por_hoja_mensual[hoja].extend(filas_mes)

                        # # ---------- EXPANSION MENSUAL ----------

                        # filas_expandidas = expandir_filas_por_mes(filas_nuevas_pdf)


                        # # ---------- AGRUPAR POR HOJA ----------
                        # idx_fecha = HEADERS_FORJA.index("Fecha de la cita AAAAMMDD")

                        # for fila_e in filas_expandidas:

                        #     fecha_raw = str(fila_e[idx_fecha]).strip()

                        #     if len(fecha_raw) != 8:
                        #         continue

                        #     year = fecha_raw[0:4]
                        #     month = fecha_raw[4:6]

                        #     hoja = f"{MESES.get(month, month)} {year}"

                        #     por_hoja_mensual[hoja].append(fila_e)

                    except Exception as e:
                        print(f"      ✖ Error procesando PDF {nombre_pdf}: {e}")

                    finally:
                        if tmp_path and os.path.exists(tmp_path):
                            try:
                                os.remove(tmp_path)
                            except Exception:
                                pass

        except Exception as e:
            print(f"  ✖ Error general en correo {m['id']}: {e}")

        if pdfs_ok > 0:
            correos_a_etiquetar.add(m["id"])
            print(f"  ✔ Correo marcado para etiquetar ({pdfs_ok} PDFs válidos)")
        else:
            print("  ✖ Correo NO apto para etiquetar (ningún PDF válido)")

        # ===============================
        # ESCRITURA BATCH (ahorro cuota) + MERGE
        # ===============================

    # Necesitamos los índices para saber qué columna agrupar y cuál fusionar
    idx_admision = HEADERS_FORJA.index("Admision")
    idx_estado = HEADERS_FORJA.index("ESTADO_ORDEN")

    if todas_filas_nuevas_base_general:
            # Capturar el rango de respuesta
            rango_base = append_filas(
                sheets,
                SPREADSHEET_ID_FORJA,
                SHEET_BASE_GENERAL,
                todas_filas_nuevas_base_general,
            )
            print(f"\n[FORJA] ✔ BASE_GENERAL_FORJA: {len(todas_filas_nuevas_base_general)} filas nuevas añadidas")

            # Ejecutar fusión de celdas
            if rango_base:
                fusionar_celdas_estado(
                    sheets,
                    SPREADSHEET_ID_FORJA,
                    SHEET_BASE_GENERAL,
                    rango_base,
                    todas_filas_nuevas_base_general,
                    idx_admision,
                    idx_estado
                )
    else:
            print("\n[FORJA] ℹ BASE_GENERAL_FORJA: no hay filas nuevas")

    if por_hoja_mensual:
            # Crear headers por hoja (1 vez por hoja)
            for hoja in por_hoja_mensual.keys():
                asegurar_headers(
                    sheets,
                    SPREADSHEET_ID_FORJA,
                    hoja,
                    HEADERS_MENSUAL,
                    HOJAS_EXISTENTES,
                )
                HOJAS_EXISTENTES.add(hoja)

            # Append batch por hoja y FUSIÓN
            for hoja, filas_mes in por_hoja_mensual.items():
                if filas_mes:
                    rango_mes = append_filas(
                        sheets,
                        SPREADSHEET_ID_FORJA,
                        hoja,
                        filas_mes,
                    )
                    
                    if rango_mes:
                        fusionar_celdas_estado(
                            sheets,
                            SPREADSHEET_ID_FORJA,
                            hoja,
                            rango_mes,
                            filas_mes,
                            idx_admision,
                            idx_estado
                        )

            print(f"[FORJA] ✔ Hojas mensuales actualizadas: {len(por_hoja_mensual)} hojas")
    else:
            print("[FORJA] ℹ No hay filas nuevas para hojas mensuales")

        # ===============================
        # Etiquetado final (solo OK)
        # ===============================
    for mid in correos_a_etiquetar:
            try:
                aplicar_etiqueta(gmail, mid, LABEL_FORJA_ID)
                print(f"[FORJA] ✔ Etiqueta FORJA aplicada al correo {mid}")
            except Exception as e:
                print(f"[FORJA] ✖ No se pudo etiquetar correo {mid}: {e}")