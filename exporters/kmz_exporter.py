import zipfile
# io import removed as it was unused
from xml.etree.ElementTree import tostring # Element, SubElement no longer needed directly here
from xml.dom import minidom
# pyproj Transformer and ProjError are not directly needed here anymore
# as _build_kml_root_element handles it.
# However, ProjError might be caught if KMLExporter.export re-raises it.
# For _generate_kml_string we expect ValueError or ProjError from the shared method.
from pyproj import ProjError

# Import the KMLExporter to use its static method
from exporters.kml_exporter import KMLExporter
# from core.coordinate_manager import GeometryType # If type constants were used

class KMZExporter:
    @staticmethod
    def _generate_kml_string(features: list[dict], hemisphere: str, zone: str) -> str:
        """
        Generates a KML string from features, hemisphere, and zone
        by calling the shared KML building logic.
        """
        # ValueError or ProjError can be raised by _build_kml_root_element
        kml_root = KMLExporter._build_kml_root_element(features, hemisphere, zone)

        xml_bytes = tostring(kml_root, encoding="utf-8", method="xml")
        parsed_xml = minidom.parseString(xml_bytes)
        return parsed_xml.toprettyxml(indent="  ")

    @staticmethod
    def export(features: list[dict], filename: str, hemisphere: str, zone: str):
        if not features:
            raise ValueError("No hay geometrías para exportar.")

        if not filename.lower().endswith(".kmz"):
            raise ValueError("El nombre de archivo debe terminar en .kmz")

        try:
            # Generar el contenido KML como string
            # This can now raise ValueError or ProjError from the shared method
            kml_content_str = KMZExporter._generate_kml_string(features, hemisphere, zone)

            kml_content_bytes = kml_content_str.encode('utf-8')

            with zipfile.ZipFile(filename, 'w', zipfile.ZIP_DEFLATED) as kmz_file:
                kmz_file.writestr('doc.kml', kml_content_bytes)

        except (ValueError, ProjError) as ve: # Catch errors from KML generation more specifically
            # Re-raise as RuntimeError for consistency with how gui.py might expect it,
            # or handle directly if gui.py is adapted. For now, wrap in RuntimeError.
            raise RuntimeError(f"Error al generar contenido KML para KMZ: {ve}")
        except Exception as e:
            raise RuntimeError(f"Error al crear el archivo KMZ '{filename}': {e}")

# Ejemplo de uso (opcional, para testing directo)
if __name__ == '__main__':
    sample_features_ok = [
        {"id": 1, "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": 2, "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": 3, "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]}
    ]
    # This feature will cause ProjError in _build_kml_root_element
    sample_features_proj_error = [
        {"id": "bad_transform_point", "type": "Punto", "coords": [(99999999.0, 4000000.0)]},
    ]

    import os
    output_dir = "test_output_kmz"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tests = [
        (sample_features_ok, "test_ok_refactored.kmz", "Norte", "18", "OK"),
        (sample_features_proj_error, "test_proj_error.kmz", "Norte", "18", "RuntimeError"), # ProjError wrapped
        ([], "test_empty_features_refactored.kmz", "Norte", "18", "ValueError"), # Caught by export()
        (sample_features_ok, "test_bad_zone_refactored.kmz", "Norte", "XYZ", "RuntimeError"), # ValueError from _build, wrapped
        (sample_features_ok, "test_bad_filename_refactored.kml", "Norte", "18", "ValueError") # Caught by export()
    ]

    for features, filename, hemisphere, zone, expected_outcome in tests:
        full_path = os.path.join(output_dir, filename)
        print(f"\nIntentando exportar KMZ: {full_path} (Esperado: {expected_outcome})")
        try:
            KMZExporter.export(features, full_path, hemisphere, zone)
            print(f"Archivo {filename} generado exitosamente.")
        except (ValueError, RuntimeError) as e:
            print(f"Error ({expected_outcome} esperado para algunos tests): {e}")
