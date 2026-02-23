from math import ceil
from datetime import datetime
from collections import defaultdict
from forja_headers import HEADERS_FORJA_INGESTA

IDX_FECHA = HEADERS_FORJA_INGESTA.index("Fecha de la cita AAAAMMDD")
IDX_TIEMPO = HEADERS_FORJA_INGESTA.index("TiempoDeTratamiento en dias")

MESES_ES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
}

def expandir_y_agrupar_por_hoja_mensual(filas):
    grupos = defaultdict(list)

    for fila in filas:
        fecha_raw = str(fila[IDX_FECHA]).strip()
        dias_raw = str(fila[IDX_TIEMPO]).strip()

        if not fecha_raw or not dias_raw:
            continue

        try:
            fecha_inicio = datetime.strptime(fecha_raw, "%Y%m%d")
            dias = int(dias_raw)
        except:
            continue

        if dias <= 0:
            continue  # tratamiento inválido

        # ====================================================
        # 🔒 REGLA ADMINISTRATIVA POR BLOQUES DE 30 DÍAS
        # ====================================================
        meses = ceil(dias / 30)

        cursor = fecha_inicio.replace(day=1)

        # índices necesarios
        IDX_CANT = HEADERS_FORJA_INGESTA.index("Cantidad")

        dias_restantes = dias

        try:
            cant_total = int(fila[IDX_CANT])
        except:
            cant_total = None


        if cant_total is not None and meses > 0:
            base_mes = cant_total // meses
            residuo = cant_total % meses
        else:
            base_mes = None
            residuo = 0
            
        while dias_restantes > 0:

            nueva = fila.copy()
            nueva[IDX_FECHA] = fila[IDX_FECHA]  # se mantiene fecha real

            # días por mes (máx 30)
            dias_mes = 30 if dias_restantes >= 30 else dias_restantes
            nueva[IDX_TIEMPO] = dias_mes

            if base_mes is not None:
                if residuo > 0:
                    nueva[IDX_CANT] = base_mes + 1
                    residuo -= 1
                else:
                    nueva[IDX_CANT] = base_mes

            nombre_hoja = f"{MESES_ES[cursor.month]} {cursor.year}"
            grupos[nombre_hoja].append(nueva)

            dias_restantes -= dias_mes



            # avanzar mes
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

    return grupos
