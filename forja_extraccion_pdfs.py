import pdfplumber
import re
from datetime import datetime
# PDF_PATH = r"C:\Users\FELIPE DIAZ SISTEMAS\Downloads\28-30, 11__Forja SI - Fórmula médica 17112988 Dario Morales Menenses  - 2025-11-28.pdf"
# PDF_PATH = r"C:\Users\FELIPE DIAZ SISTEMAS\Downloads\1-12__Forja SI - Fórmula médica 33120020 CARMEN ELENA DEL VALLE DE AGUILAR Formula externa - 2025-12-01.pdf"
# PDF_PATH = r"C:\Users\FELIPE DIAZ SISTEMAS\Downloads\28-30, 11__Forja SI - Fórmula médica 20000154 MARIA INES PINZON REYES  - 2025-11-30.pdf"
PDF_PATH = r"C:\Users\FELIPE DIAZ SISTEMAS\Downloads\28-30, 11__Forja SI - Fórmula médica 427446 PASTOR  CARDENAS CARDENAS Formula externa - 2025-11-29 (1).pdf"
def normalizar_fecha(fecha):
    try:
        return datetime.strptime(fecha, "%Y-%m-%d").strftime("%Y%m%d")
    except:
        return ""
    
def extraer_dias_tratamiento(texto: str) -> str:
    if not texto:
        return ""

    # Normalización mínima para unir "Por" + "90 días"
    t = re.sub(r"\s*\n\s*", " ", texto)
    t = re.sub(r"\s{2,}", " ", t)
    t = t.lower()

    # 1) Caso normal
    m = re.search(r"por\s+(\d+)\s*d[ií]as", t)
    if m:
        return m.group(1)

    # 2) Caso partido: "Por ... 90 días"
    m = re.search(r"por\s+.*?(\d+)\s*d[ií]as", t)
    if m:
        return m.group(1)

    # 3) Caso sin palabra días: "Por 90"
    m = re.search(r"por\s+(\d+)\b", t)
    if m:
        return m.group(1)

    return ""

    
def extraer_formula_laxa(texto):
    """
    Extractor de respaldo para PDFs FORJA problemáticos.
    Menos estricto, solo para rescate.
    """
    datos = {
        "numero_documento": "",
        "medicamentos": []
    }

    m = re.search(r"Identificación:\s*(\d+)", texto)
    if m:
        datos["numero_documento"] = m.group(1)

    # Bloque MEDICAMENTOS (mismo inicio/fin)
    bloque_match = re.search(
        r"MEDICAMENTOS(.*?)(?:Esta fórmula tiene validez|Esta formula tiene validez)",
        texto,
        re.DOTALL | re.IGNORECASE
    )
    if not bloque_match:
        return datos

    bloque = bloque_match.group(1)

    # Normalización fuerte SOLO aquí
    bloque = re.sub(r"\s*\n\s*", " ", bloque)

    # Patrón laxo: Administrar + Diagnostico
    patron = re.compile(
        r"""
        (
            .*?
            Administrar.*?
            Diagnostico:.*?\([A-Za-z]\d+[A-Za-z0-9]*\)
        )
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE
    )

    for m in patron.finditer(bloque):
        texto_med = m.group(1)
        texto_bruto = re.sub(r"\s+", " ", texto_med).strip()

        nombre = limpiar_numero_letras(
            extraer_nombre_presentacion(texto_med)
        )

        dx = ""
        dxs = re.findall(r"\(([A-Za-z]\d+[A-Za-z0-9]*)\)", texto_med)
        if dxs:
            dx = dxs[-1].upper()

        dias = ""
        md = re.search(r"Por\s+(\d+)\s*d[ií]as", texto_med, re.IGNORECASE)
        if md:
            dias = md.group(1)

        datos["medicamentos"].append({
            "nombre_medicamento": nombre,
            "dx": dx,
            "cantidad": "",      # ⚠ puede quedar vacío
            "dias": dias,
            "posologia": ""      # ⚠ opcional en rescate
        })
    datos["rescatado"] = True

    return datos



def limpiar_numero_letras(texto: str) -> str:
    """
    Elimina patrones tipo:
    - 90 Noventa
    - 180 Ciento ochenta
    - 90 90
    - Cada cada
    """
    if not texto:
        return texto

    # 1) Número + palabra en letras


    texto = re.sub(
        r"\b\d+\s+(?:"
        r"uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
        r"once|doce|trece|catorce|quince|dieciséis|diecisiete|"
        r"dieciocho|diecinueve|veinte|treinta|cuarenta|cincuenta|"
        r"sesenta|setenta|ochenta|noventa|cien|ciento|doscientos|"
        r"trescientos|cuatrocientos|quinientos|seiscientos|"
        r"setecientos|ochocientos|novecientos"
        r")(?:\s+y\s+\w+)?\b",
        "",
        texto,
        flags=re.IGNORECASE
    )

    # 2) Número número (90 90, 180 180)
    texto = re.sub(r"\b(\d+)\s+\1\b", r"\1", texto)

    # 3) "Cada cada"
    texto = re.sub(r"\bcada\s+cada\b", "cada", texto, flags=re.IGNORECASE)

    # Limpieza estética final
    texto = re.sub(r"\s{2,}", " ", texto)
    texto = re.sub(r";\s*;", ";", texto)

    return texto.strip()


def limpiar_posologia(posologia: str) -> str:
    """
    Limpieza específica para posología.

    Reglas:
    1. Elimina duplicados explícitos:
       - ocho (8) → 8
       - 8 (ocho) → 8
       - ocho 8 → 8
       - 8 ocho → 8
    2. Elimina palabras numéricas SUELTAS:
       - 'Vía setenta oral' → 'Vía oral'
       - 'Cada doce horas' → 'Cada horas'
    3. Elimina duplicados puros:
       - '12 12 horas' → '12 horas'
    4. Corrige repeticiones estructurales:
       - 'cada cada' → 'cada'
       - 'vía vía' → 'vía'
    """
    if not posologia:
        return posologia

    palabras_numero = (
        "uno|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|"
        "once|doce|trece|catorce|quince|dieciséis|diecisiete|"
        "dieciocho|diecinueve|veinte|treinta|cuarenta|cincuenta|"
        "sesenta|setenta|ochenta|noventa|cien|ciento"
    )

    # 1) palabra (número) → número
    posologia = re.sub(
        rf"\b({palabras_numero})\s*\(\s*(\d+)\s*\)",
        r"\2",
        posologia,
        flags=re.IGNORECASE
    )

    # 2) número (palabra) → número
    posologia = re.sub(
        rf"\b(\d+)\s*\(\s*({palabras_numero})\s*\)",
        r"\1",
        posologia,
        flags=re.IGNORECASE
    )

    # 3) palabra número → número
    posologia = re.sub(
        rf"\b({palabras_numero})\s+(\d+)\b",
        r"\2",
        posologia,
        flags=re.IGNORECASE
    )

    # 4) número palabra → número
    posologia = re.sub(
        rf"\b(\d+)\s+({palabras_numero})\b",
        r"\1",
        posologia,
        flags=re.IGNORECASE
    )

    # 5) eliminar palabras numéricas SUELTAS
    posologia = re.sub(
        rf"\b({palabras_numero})\b",
        "",
        posologia,
        flags=re.IGNORECASE
    )

    # 6) número número (12 12)
    posologia = re.sub(r"\b(\d+)\s+\1\b", r"\1", posologia)

    # 7) repeticiones estructurales
    posologia = re.sub(r"\bcada\s+cada\b", "cada", posologia, flags=re.IGNORECASE)
    posologia = re.sub(r"\bvía\s+vía\b", "vía", posologia, flags=re.IGNORECASE)

    # 8) limpieza estética final
    posologia = re.sub(r"\(\s*\)", "", posologia)
    posologia = re.sub(r"\s{2,}", " ", posologia)
    posologia = re.sub(r";\s*;", ";", posologia)

    
    # 9) eliminar ; y . (SOLO AQUÍ)
    posologia = posologia.replace(";", " ")
    posologia = posologia.replace(".", " ")

    posologia = re.sub(r"\s{2,}", " ", posologia)

    return posologia.strip()



# ==============================
# GLOBALS DEL PDF (SOLO 1 VEZ)
# ==============================
def extraer_globales(texto):
    data = {
        "tipo_doc": "CC",
        "documento": "",
        "nit_empresa": "",
        "contactos": [],
        "fecha_cita": "",
       
    }

    m = re.search(r"Identificación:\s*(\d+)", texto)
    if m:
        data["documento"] = m.group(1)

   

    m = re.search(r"NIT\s*([\d\.\-]+)", texto)
    if m:
        data["nit_empresa"] = re.sub(r"-\d+$", "", m.group(1))


    tels = re.findall(r"(3\d{9})", texto)
    data["contactos"] = list(dict.fromkeys(tels))

    # ==========================
    # FECHA CITA FORJA (ROBUSTA)
    # ==========================

    m = re.search(
        r"Fecha\s*:?\s*(\d{4}-\d{2}-\d{2})",
        texto,
        re.IGNORECASE
    )

    if m:
        fecha_raw = m.group(1)
        data["fecha_cita"] = normalizar_fecha(fecha_raw)
    else:
        data["fecha_cita"] = ""

    # BLOQUEO DE BASURA CLINICA (90, 60, 120)
    if data["fecha_cita"] and len(data["fecha_cita"]) != 8:
        data["fecha_cita"] = ""

    return data



def extraer_nombre_presentacion(texto: str) -> str:
    """
    Extrae nombre del medicamento + presentación (forma y concentración),
    excluyendo posología, vía, frecuencia y duración.
    """
    # Cortar en "Administrar"
    base = texto.split("Administrar")[0]

    # Eliminar saltos raros
    base = base.replace("\n", " ")

    # Normalizar espacios
    base = re.sub(r"\s{2,}", " ", base).strip()

    # Limpieza de conectores inútiles
    base = re.sub(r";\s*", " ", base)

    return base.strip()


def extraer_formula(texto):
    datos = {
        "numero_documento": "",
        "medicamentos": []
    }

    # Documento del paciente
    m = re.search(r"Identificación:\s*(\d+)", texto)
    if m:
        datos["numero_documento"] = m.group(1)

    # ---------- BLOQUE MEDICAMENTOS ----------
    bloque_match = re.search(
        r"MEDICAMENTOS(.*?)(?:Esta fórmula tiene validez|Esta formula tiene validez)",
        texto,
        re.DOTALL | re.IGNORECASE
    )

    if not bloque_match:
        return datos

    bloque = bloque_match.group(1)

    # Eliminar encabezado fijo
    bloque = re.sub(
        r"Medicamentos,\s*concentración\s*y\s*Cantidad.*?Letras",
        "",
        bloque,
        flags=re.IGNORECASE | re.DOTALL
    )

    # ---------- PATRÓN DE MEDICAMENTO ----------
    patron_medicamento = re.compile(
        r"""
        (
            .*?
            Diagnostico:.*?\([A-Za-z]\d+[A-Za-z0-9]*\)\.
        )
        """,
        re.IGNORECASE | re.DOTALL | re.VERBOSE
    )


    for match in patron_medicamento.finditer(bloque):
        texto_med = match.group(1).strip()
        nombre_medicamento = limpiar_numero_letras(
            extraer_nombre_presentacion(texto_med)
        )
        texto_bruto = re.sub(r"\s+", " ", texto_med).strip()

        # ---------- DX ----------
        dx_med = ""
        dxs = re.findall(r"\(([A-Za-z]\d+[A-Za-z0-9]*)\)", texto_med)
        if dxs:
            dx_med = dxs[-1].upper()

        # ---------- CANTIDAD ----------
        cantidad = ""
        m_cant = re.search(
            r"\b([1-9]\d{0,2}|400)\s+[A-Za-zÁÉÍÓÚáéíóú ]+\n",
            texto_med
        )
        if m_cant:
            cantidad = m_cant.group(1)

        # ---------- DÍAS ----------
        # ---------- DÍAS (ROBUSTO) ----------
        dias = extraer_dias_tratamiento(texto_med)


        # ---------- POSOLOGÍA (CORRECTA) ----------
        # ---------- POSOLOGÍA (EXACTA, SIN INTERPRETAR) ----------
        posologia = ""

        # Normalizar espacios para regex
        texto_norm = texto_bruto

        partes_posologia = []

        # Administrar { ... ; }
        m_admin = re.search(
            r"(Administrar\s+.*?;)",
            texto_norm,
            re.IGNORECASE
        )
        if m_admin:
            partes_posologia.append(m_admin.group(1).strip())

        # Vía { ... ; }
        m_via = re.search(
            r"(Vía\s+.*?;)",
            texto_norm,
            re.IGNORECASE
        )
        if m_via:
            partes_posologia.append(m_via.group(1).strip())

        # Cada { ... ; }
        m_cada = re.search(
            r"(Cada\s+.*?;)",
            texto_norm,
            re.IGNORECASE
        )
        if m_cada:
            partes_posologia.append(m_cada.group(1).strip())

        if partes_posologia:
            posologia = " ".join(partes_posologia)
            posologia = limpiar_numero_letras(posologia)

            posologia = limpiar_posologia(posologia)
  


        # ---------- APPEND ----------
        datos["medicamentos"].append({
            "nombre_medicamento": nombre_medicamento,

            # "texto_bruto": texto_med,
            "dx": dx_med,
            "cantidad": cantidad,
            "dias": dias,
            "posologia": posologia
        })
    datos["rescatado"] = False

# ✅ ESTE return VA AQUÍ, FUERA DEL LOOP
    return datos


def extraer_id_drive(link_pdf: str) -> str:
    """
    Extrae el ID del archivo de un link tipo:
    https://drive.google.com/file/d/ID/view?usp=...
    """
    if not link_pdf:
        return ""

    partes = link_pdf.split("/d/")
    if len(partes) < 2:
        return ""

    return partes[1].split("/")[0]

# ==============================
# PROCESAR PDF
# ==============================
def procesar_pdf(pdf_path,link_pdf):
    resultado = {
        "globales": {},
        "formulas": []
    }
   
    drive_id = extraer_id_drive(link_pdf)
    if not drive_id:
        raise ValueError("No se pudo extraer drive_id del link_pdf")



    with pdfplumber.open(pdf_path) as pdf:
        for idx, page in enumerate(pdf.pages, start=1):

            if idx % 2 == 0:
                continue

            w, h = page.width, page.height
            texto = page.crop((0, 0, w/2, h)).extract_text() or ""

            if "Original" not in texto:
                continue

            if not resultado["globales"]:
                resultado["globales"] = extraer_globales(texto)

            formula = extraer_formula(texto)
            if not formula["medicamentos"]:
                formula = extraer_formula_laxa(texto)
            
            documento = resultado['globales'].get('documento','').strip().upper()
            fecha = resultado['globales'].get('fecha_cita','').strip()

            if not documento or not fecha:
                raise ValueError("Documento o fecha vacíos al construir formula_key")

            formula["formula_key"] = f"{documento}-{fecha}-{drive_id}"


            if formula["medicamentos"]:
                resultado["formulas"].append(formula)
                        
    
    return resultado

