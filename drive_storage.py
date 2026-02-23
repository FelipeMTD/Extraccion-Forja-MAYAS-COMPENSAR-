# drive_storage.py
import io
from datetime import datetime
from googleapiclient.http import MediaIoBaseUpload

# ===============================
# CACHE EN MEMORIA DE CARPETAS
# Key: (parent_id, folder_name)
# Value: folder_id
# Vive solo durante la ejecución
# ===============================
_DRIVE_FOLDER_CACHE = {}


def asegurar_carpeta(service_drive, nombre: str, parent_id: str):
    cache_key = (parent_id, nombre)
    if cache_key in _DRIVE_FOLDER_CACHE:
        return _DRIVE_FOLDER_CACHE[cache_key]

    q = (
        "mimeType='application/vnd.google-apps.folder' and "
        f"name='{nombre}' and '{parent_id}' in parents and trashed=false"
    )
    res = service_drive.files().list(
        q=q,
        fields="files(id,name)",
        pageSize=1
    ).execute()

    files = res.get("files", [])
    if files:
        folder_id = files[0]["id"]
    else:
        meta = {
            "name": nombre,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id],
        }
        carpeta = service_drive.files().create(
            body=meta,
            fields="id"
        ).execute()
        folder_id = carpeta["id"]

    _DRIVE_FOLDER_CACHE[cache_key] = folder_id
    return folder_id


def guardar_pdf_en_drive(
    service_drive,
    root_forja_id: str,
    nombre_pdf: str,
    data_pdf: bytes,
    fecha: datetime,
):
    mes = fecha.strftime("%Y-%m")
    dia = fecha.strftime("%Y-%m-%d")

    id_mes = asegurar_carpeta(service_drive, mes, root_forja_id)
    id_dia = asegurar_carpeta(service_drive, dia, id_mes)

    media = MediaIoBaseUpload(
        io.BytesIO(data_pdf),
        mimetype="application/pdf",
        resumable=False
    )

    meta = {
        "name": nombre_pdf,
        "parents": [id_dia]
    }

    f = service_drive.files().create(
        body=meta,
        media_body=media,
        fields="id, webViewLink"
    ).execute()

    return f
