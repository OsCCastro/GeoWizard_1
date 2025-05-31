# GeoWizard

GeoWizard es una aplicación de escritorio para la gestión y visualización de coordenadas geográficas. Permite a los usuarios ingresar coordenadas, definir geometrías (puntos, polilíneas, polígonos) y exportarlas a formatos comunes.

## Características (Planificadas/Implementadas)

*   Entrada manual de coordenadas UTM.
*   Visualización de geometrías en un lienzo.
*   Exportación a KML (implementado).
*   Exportación a KMZ, Shapefile (planificado).
*   Importación desde CSV, KML (planificado).
*   Selección de Hemisferio y Zona UTM.
*   Previsualización en tiempo real.

## Requisitos Previos

*   Python 3.7+
*   pip (Python package installer)

## Instalación

1.  Clona este repositorio:
    ```bash
    git clone [URL de tu repositorio aquí]
    cd GeoWizard_1
    ```
2.  (Recomendado) Crea y activa un entorno virtual:
    ```bash
    python -m venv venv
    # En Windows
    # venv\Scripts\activate
    # En macOS/Linux
    # source venv/bin/activate
    ```
3.  Instala las dependencias:
    ```bash
    pip install -r requirements.txt
    ```

## Uso

Para ejecutar la aplicación:
```bash
python main.py
```

## Licencia

Este proyecto está bajo la Licencia MIT. Ver el archivo LICENSE para más detalles.