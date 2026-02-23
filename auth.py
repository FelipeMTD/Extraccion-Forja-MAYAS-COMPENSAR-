# auth.py

SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]

SERVICE_ACCOUNT_FILE = "forja1.json"
IMPERSONAR = "juan.diaz@mtd.net.co"
# IMPERSONAR = "mallas.compensar@mtd.net.co"

# def obtener_servicios():

#     creds = service_account.Credentials.from_service_account_file(
#         SERVICE_ACCOUNT_FILE,
#         scopes=SCOPES,
#         subject=IMPERSONAR
#     )

#     gmail = build("gmail", "v1", credentials=creds)
#     drive = build("drive", "v3", credentials=creds)
#     sheets = build("sheets", "v4", credentials=creds)

#     return gmail, drive, sheets
def obtener_servicios():

    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=SCOPES,
        subject=IMPERSONAR
    )

    gmail = build("gmail", "v1", credentials=creds)
    drive = build("drive", "v3", credentials=creds)
    sheets = build("sheets", "v4", credentials=creds)

    return gmail, drive, sheets
