import zipfile
import io # io is not strictly needed with the current _generate_kml_string, but good if we change it to use StringIO
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pyproj import Transformer

# from core.coordinate_manager import GeometryType # Si se usan constantes para geom_type

class KMZExporter:
    @staticmethod
    def _generate_kml_string(features: list[dict], hemisphere: str, zone: str) -> str:
        # Esta lógica es una copia adaptada de KMLExporter.export,
        # pero devuelve el string KML en lugar de escribir a archivo.
        # Se podría refactorizar KMLExporter para exponer esta lógica.

        # Validar zona como entero
        try:
            z = int(zone)
        except ValueError:
            raise ValueError(f"La zona UTM '{zone}' debe ser un número entero.")

        epsg_from = 32600 + z if hemisphere.lower()=="norte" else 32700 + z
        # always_xy=True asegura (lon, lat) para EPSG:4326
        transformer = Transformer.from_crs(f"EPSG:{epsg_from}", "EPSG:4326", always_xy=True)

        kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc = SubElement(kml, "Document")

        for feat in features:
            if not feat.get("coords"): # Verificar si hay coordenadas
                # Omitir este feature o manejar error como se prefiera
                print(f"Advertencia: Feature ID {feat.get('id')} no tiene coordenadas. Se omitirá.")
                continue

            pm = SubElement(doc, "Placemark")
            SubElement(pm, "name").text = str(feat.get("id", "SinID")) # Usar .get con default

            # Descripción UTM
            # Asegurarse de que coords no esté vacío antes de acceder a coords[0]
            x0, y0 = feat["coords"][0]
            desc_text = (
                f"Zona: {zone} ({hemisphere})\n"
                f"Este: {x0:.2f} m\n"
                f"Norte: {y0:.2f} m"
            )
            desc = SubElement(pm, "description")
            desc.text = f"<![CDATA[{desc_text}]]>"

            geom_type = feat.get("type")

            # Usar constantes/enum aquí sería mejor (ej. GeometryType.PUNTO)
            # Mantengo los strings literales por ahora para que coincida con el input de gui.py
            if geom_type == "Punto" or geom_type == "Point":
                if not feat["coords"]: continue # Saltear si no hay coords
                geom = SubElement(pm, "Point")
                # Point tiene una sola coordenada
                lon, lat = transformer.transform(feat["coords"][0][0], feat["coords"][0][1])
                SubElement(geom, "coordinates").text = f"{lon:.6f},{lat:.6f},0"
            elif geom_type == "Polilínea" or geom_type == "LineString":
                if len(feat["coords"]) < 2: continue # Saltear si no hay suficientes coords
                geom = SubElement(pm, "LineString")
                coords_text_list = []
                for x,y in feat["coords"]:
                    lon, lat = transformer.transform(x, y)
                    coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                SubElement(geom, "coordinates").text = " ".join(coords_text_list)
            elif geom_type == "Polígono" or geom_type == "Polygon":
                if len(feat["coords"]) < 3: continue # Saltear si no hay suficientes coords
                poly = SubElement(pm, "Polygon")
                obb  = SubElement(poly, "outerBoundaryIs")
                lr   = SubElement(obb, "LinearRing")
                coords_text_list = []
                # El cierre del anillo es manejado aquí
                ring = feat["coords"] + [feat["coords"][0]]
                for x,y in ring:
                    lon, lat = transformer.transform(x, y)
                    coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                SubElement(lr, "coordinates").text = " ".join(coords_text_list)
            else:
                print(f"Advertencia: Tipo de geometría '{geom_type}' para feature ID {feat.get('id')} no soportado por KMZExporter. Se omitirá.")
                continue # Importante para no intentar acceder a 'geom' si no se creó

        xml_bytes = tostring(kml, encoding="utf-8", method="xml")
        parsed_xml = minidom.parseString(xml_bytes)
        # toprettyxml devuelve string si encoding no se especifica, o bytes si sí.
        return parsed_xml.toprettyxml(indent="  ") # Devuelve string (UTF-8 por defecto en Python 3)

    @staticmethod
    def export(features: list[dict], filename: str, hemisphere: str, zone: str):
        if not features:
            raise ValueError("No hay geometrías para exportar.")

        if not filename.lower().endswith(".kmz"):
            raise ValueError("El nombre de archivo debe terminar en .kmz")

        try:
            # Generar el contenido KML como string
            kml_content_str = KMZExporter._generate_kml_string(features, hemisphere, zone)

            # El KML string debe ser encodeado a bytes para escribir en el archivo zip
            kml_content_bytes = kml_content_str.encode('utf-8')

            with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as kmz_file:
                # Escribir el contenido KML (bytes) en 'doc.kml' dentro del archivo KMZ
                kmz_file.writestr('doc.kml', kml_content_bytes)
        except ValueError as ve:
            raise ve
        except Exception as e:
            raise RuntimeError(f"Error al crear el archivo KMZ '{filename}': {e}")

# Ejemplo de uso (opcional, para testing directo)
if __name__ == '__main__':
    sample_features_ok = [
        {"id": 1, "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": 2, "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": 3, "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]}
    ]
    sample_features_bad_type = [
        {"id": 4, "type": "Círculo", "coords": [(500000.0, 4000000.0)]}
    ]
    sample_features_no_coords = [
        {"id": 5, "type": "Punto", "coords": []}
    ]

    # Crear directorio 'test_output' si no existe
    import os
    output_dir = "test_output_kmz" # Directorio específico para KMZ
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tests = [
        (sample_features_ok, "test_ok.kmz", "Norte", "18", "OK"),
        (sample_features_bad_type, "test_bad_type.kmz", "Norte", "18", "OK (con advertencia)"),
        # (sample_features_no_coords, "test_no_coords.kmz", "Norte", "18", "OK (con advertencia)"), # Ya se valida en _generate_kml_string
        # ([], "test_empty_features.kmz", "Norte", "18", "ValueError"), # Ya se valida en export
        (sample_features_ok, "test_bad_zone.kmz", "Norte", "XYZ", "ValueError"),
        (sample_features_ok, "test_bad_filename.kml", "Norte", "18", "ValueError")
    ]

    for features, filename, hemisphere, zone, expected_outcome in tests:
        full_path = os.path.join(output_dir, filename)
        print(f"\nIntentando exportar: {full_path} (Esperado: {expected_outcome})")
        try:
            KMZExporter.export(features, full_path, hemisphere, zone)
            print(f"Archivo {filename} generado exitosamente.")
        except (ValueError, RuntimeError) as e:
            print(f"Error (esperado para algunos tests): {e}")
