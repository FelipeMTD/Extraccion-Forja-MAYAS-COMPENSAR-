# date_picker.py
import tkinter as tk
from tkcalendar import DateEntry
from datetime import datetime


def seleccionar_rango_fechas():
    result = {}

    def confirmar():
        result["inicio"] = fecha_inicio.get_date()
        result["fin"] = fecha_fin.get_date()
        root.destroy()

    root = tk.Tk()
    root.title("Seleccionar rango de fechas FORJA")
    root.geometry("300x200")
    root.resizable(False, False)

    tk.Label(root, text="Fecha inicio").pack(pady=5)
    fecha_inicio = DateEntry(
        root,
        width=12,
        background="darkblue",
        foreground="white",
        date_pattern="yyyy-mm-dd"
    )
    fecha_inicio.pack(pady=5)

    tk.Label(root, text="Fecha fin").pack(pady=5)
    fecha_fin = DateEntry(
        root,
        width=12,
        background="darkblue",
        foreground="white",
        date_pattern="yyyy-mm-dd"
    )
    fecha_fin.pack(pady=5)

    tk.Button(root, text="Aceptar", command=confirmar).pack(pady=15)

    root.mainloop()

    if "inicio" not in result or "fin" not in result:
        raise RuntimeError("No se seleccionó el rango de fechas")

    return (
        datetime.combine(result["inicio"], datetime.min.time()),
        datetime.combine(result["fin"], datetime.min.time()),
    )
