# gmail_reader.py
from datetime import timedelta
import base64


def buscar_mensajes(service_gmail, remitentes, fecha_inicio, fecha_fin,label_excluir):
    if isinstance(remitentes, list):
        from_query = " OR ".join([f"from:{r}" for r in remitentes])
        from_query = f"({from_query})"
    else:
        from_query = f"from:{remitentes}"

    query = (
        f"{from_query} "
        f"after:{fecha_inicio.strftime('%Y/%m/%d')} "
        f"before:{(fecha_fin + timedelta(days=1)).strftime('%Y/%m/%d')} "
        f"-label:{label_excluir}"
    )



    mensajes = []
    req = service_gmail.users().messages().list(userId="me", q=query)

    while req:
        res = req.execute()
        mensajes.extend(res.get("messages", []))
        req = service_gmail.users().messages().list_next(req, res)

    return mensajes


def obtener_adjuntos(service_gmail, msg_id):
    msg = service_gmail.users().messages().get(
        userId="me",
        id=msg_id
    ).execute()

    adjuntos = []
    payload = msg.get("payload", {})
    parts = payload.get("parts", [])

    for p in parts:
        filename = p.get("filename")
        body = p.get("body", {})
        att_id = body.get("attachmentId")

        if filename and att_id:
            att = service_gmail.users().messages().attachments().get(
                userId="me",
                messageId=msg_id,
                id=att_id
            ).execute()

            data = base64.urlsafe_b64decode(att["data"])
            adjuntos.append((filename, data))

    return adjuntos
