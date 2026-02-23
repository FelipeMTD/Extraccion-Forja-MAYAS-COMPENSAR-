
# sheets_writer.py

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
            range=f"{sheet_name}!A1",
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
    Agrega filas al final de la hoja.
    """
    if not filas:
        return

    service_sheets.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{sheet_name}!A1",
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": filas},
    ).execute()
