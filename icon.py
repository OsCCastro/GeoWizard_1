import os
import re

ruta_iconos = "icons"  # Cambia esto si están en otra carpeta

for nombre in os.listdir(ruta_iconos):
    if nombre.endswith(".svg"):
        ruta = os.path.join(ruta_iconos, nombre)
        with open(ruta, "r", encoding="utf-8") as f:
            contenido = f.read()

        # Reemplaza cualquier fill='...' o fill="..." por fill="currentColor"
        nuevo = re.sub(r'fill\s*=\s*["\']#[0-9a-fA-F]{3,6}["\']', 'fill="currentColor"', contenido)
        nuevo = re.sub(r'fill\s*=\s*["\'](black|white|none)["\']', 'fill="currentColor"', nuevo)

        with open(ruta, "w", encoding="utf-8") as f:
            f.write(nuevo)

        print(f"✔️ Modificado: {nombre}")
