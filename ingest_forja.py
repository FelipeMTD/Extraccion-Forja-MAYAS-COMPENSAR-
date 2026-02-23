from datetime import datetime
from gmail_reader import buscar_mensajes, obtener_adjuntos
from zip_handler import extraer_pdfs
from drive_storage import guardar_pdf
from gmail_labels import aplicar_etiqueta

def ejecutar_ingesta_forja(
    service_gmail,
    service_drive,
    remitente: str,
    fecha_inicio: datetime,
    fecha_fin: datetime,
    drive_root_id: str,
    label_ok: str,
    label_error: str,
    label_sin_pdf: str
):
    mensajes = buscar_mensajes(service_gmail, remitente, fecha_inicio, fecha_fin)

    for m in mensajes:
        msg_id = m["id"]
        try:
            adjuntos = obtener_adjuntos(service_gmail, msg_id)

            pdfs_totales = []

            for nombre, data in adjuntos:
                pdfs = extraer_pdfs(data, nombre)
                pdfs_totales.extend(pdfs)

            if not pdfs_totales:
                aplicar_etiqueta(service_gmail, msg_id, label_sin_pdf)
                continue

            for nombre_pdf, data_pdf in pdfs_totales:
                guardar_pdf(
                    service_drive,
                    drive_root_id,
                    nombre_pdf,
                    data_pdf,
                    fecha_inicio  # o fecha del correo si quieres
                )

            aplicar_etiqueta(service_gmail, msg_id, label_ok)

        except Exception:
            aplicar_etiqueta(service_gmail, msg_id, label_error)
