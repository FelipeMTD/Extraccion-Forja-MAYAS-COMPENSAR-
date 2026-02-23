# sheets_writer.py
import re

def asegurar_headers(
    service_sheets,
    spreadsheet_id: str,
    sheet_name: str,
    headers: list[str],
    hojas_existentes: set[str],
    
):
    """
    Asegura que la hoja exista y tenga headers.
    - NO hace lecturas (evita cuota 429).
    - Usa cache local de hojas_existentes.
    """

    # Crear hoja solo si no existe
    if sheet_name not in hojas_existentes:
        print(f"[INFO] Creando hoja {sheet_name}")

        service_sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={
                "requests": [{
                    "addSheet": {
                        "properties": {
                            "title": sheet_name
                        }
                    }
                }]
            }
        ).execute()

        # Registrar en cache local
        hojas_existentes.add(sheet_name)

        # Escribir headers directamente
        service_sheets.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{sheet_name}'!A1",
            valueInputOption="RAW",
            body={"values": [headers]},
        ).execute()


def append_filas(
    service_sheets,
    spreadsheet_id: str,
    sheet_name: str,
    filas: list[list],
):
    """
    Agrega filas al final de la hoja y retorna el rango exacto donde se insertaron.
    """
    if not filas:
        return None

    resp = service_sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": filas},
    ).execute()
    
    # Devuelve el rango actualizado, ej: "'BASE_GENERAL_FORJA'!A15:AW25"
    return resp.get("updates", {}).get("updatedRange")


def fusionar_celdas_estado(
    service_sheets,
    spreadsheet_id: str,
    sheet_name: str,
    rango_actualizado: str,
    filas: list[list],
    idx_admision: int,
    idx_estado: int
):
    """
    Calcula dinámicamente qué filas pertenecen a la misma 'Admision' 
    y envía un batchUpdate para hacer Merge (combinar celdas) en la columna de Estado.
    """
    if not rango_actualizado or not filas:
        return

    # 1. Obtener el sheetId numérico (necesario para hacer Merge)
    ss = service_sheets.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    sheet_id = None
    for s in ss.get("sheets", []):
        if s["properties"]["title"] == sheet_name:
            sheet_id = s["properties"]["sheetId"]
            break
    
    if sheet_id is None:
        return

    # 2. Extraer la fila de inicio (Sheets API usa base-0 para los índices de Merge)
    # rango_actualizado ej: "'Enero 2025'!A15:AW25" o "FORJA!A15:Z20"
    parte_rango = rango_actualizado.split("!")[-1] if "!" in rango_actualizado else rango_actualizado
    celda_inicio = parte_rango.split(":")[0]  # Ej: 'A15'
    
    fila_str = re.sub(r"\D", "", celda_inicio) # Extrae solo el número '15'
    start_row_0based = int(fila_str) - 1

    # 3. Calcular los rangos exactos a fusionar agrupando por Admision
    requests = []
    current_val = None
    group_start = start_row_0based
    count = 0

    for i, fila in enumerate(filas):
        val = fila[idx_admision] if idx_admision < len(fila) else None
        
        if val != current_val:
            # Si el grupo anterior tenía más de 1 fila, preparamos el Merge
            if count > 1:
                requests.append({
                    "mergeCells": {
                        "range": {
                            "sheetId": sheet_id,
                            "startRowIndex": group_start,
                            "endRowIndex": group_start + count,
                            "startColumnIndex": idx_estado,
                            "endColumnIndex": idx_estado + 1 # +1 porque endColumn es exclusivo
                        },
                        "mergeType": "MERGE_ALL"
                    }
                })
            # Iniciar nuevo grupo
            current_val = val
            group_start = start_row_0based + i
            count = 1
        else:
            count += 1
            
    # Procesar el último grupo si llegó al final
    if count > 1:
        requests.append({
            "mergeCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": group_start,
                    "endRowIndex": group_start + count,
                    "startColumnIndex": idx_estado,
                    "endColumnIndex": idx_estado + 1
                },
                "mergeType": "MERGE_ALL"
            }
        })

    # 4. Ejecutar la llamada de fusión en la API
    if requests:
        service_sheets.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": requests}
        ).execute()
        print(f"      [INFO] {len(requests)} grupos de celdas combinados en hoja '{sheet_name}'.")