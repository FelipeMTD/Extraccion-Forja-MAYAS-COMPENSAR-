def obtener_o_crear_label(service_gmail, nombre_label):
    labels = (
        service_gmail.users()
        .labels()
        .list(userId="me")
        .execute()
        .get("labels", [])
    )

    for lbl in labels:
        if lbl["name"] == nombre_label:
            return lbl["id"]

    # Si no existe, crearla
    label = (
        service_gmail.users()
        .labels()
        .create(
            userId="me",
            body={
                "name": nombre_label,
                "labelListVisibility": "labelShow",
                "messageListVisibility": "show",
            },
        )
        .execute()
    )

    return label["id"]


def aplicar_etiqueta(service_gmail, message_id, label_id):
    service_gmail.users().messages().modify(
        userId="me",
        id=message_id,
        body={
            "addLabelIds": [label_id],
            "removeLabelIds": ["INBOX"],
        },
    ).execute()
