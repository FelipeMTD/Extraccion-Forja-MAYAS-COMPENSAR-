import io
import zipfile
from pathlib import Path
import rarfile

import os


import sys

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UNRAR_PATH = resource_path("UnRAR.exe")

if os.path.exists(UNRAR_PATH):
    rarfile.UNRAR_TOOL = UNRAR_PATH
    print(f"[INFO] Usando unrar local: {UNRAR_PATH}")
else:
    print(f"[WARN] unrar.exe NO encontrado en {UNRAR_PATH}")

def extraer_pdfs(data: bytes, nombre: str):
    nombre = nombre.lower()

    # PDF directo
    if nombre.endswith(".pdf"):
        return [(Path(nombre).name, data)]

    pdfs = []

    # ZIP
    if nombre.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for f in z.namelist():
                if f.lower().endswith(".pdf"):
                    pdfs.append((Path(f).name, z.read(f)))
        return pdfs

    # RAR (PROTEGIDO)
    if nombre.endswith(".rar"):
        try:
            with rarfile.RarFile(io.BytesIO(data)) as r:
                for f in r.namelist():
                    if f.lower().endswith(".pdf"):
                        pdfs.append((Path(f).name, r.read(f)))
        except rarfile.RarCannotExec:
            print(f"[WARN] RAR ignorado (unrar no disponible): {nombre}")
        except rarfile.BadRarFile:
            print(f"[WARN] RAR corrupto: {nombre}")
        except Exception as e:
            print(f"[WARN] Error leyendo RAR {nombre}: {e}")

        return pdfs

    return []
