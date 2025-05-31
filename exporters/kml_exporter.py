# exporters/kml_exporter.py
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pyproj import Transformer, ProjError

# Import GeometryType to use its constants for type checking if desired,
# though current implementation uses strings.
from core.coordinate_manager import GeometryType

class KMLExporter:
    @staticmethod
    def _build_kml_root_element(features: list[dict], hemisphere: str, zone_str: str) -> Element:
        """
        Builds the KML XML root Element from features, hemisphere, and zone.
        Handles coordinate transformations and KML structure generation.
        Raises ValueError for invalid zone/hemisphere, ProjError for CRS issues.
        """
        try:
            zone_int = int(zone_str)
            if not (1 <= zone_int <= 60):
                raise ValueError(f"Zona UTM '{zone_str}' inválida. Debe estar entre 1 y 60.")
            if hemisphere.lower() not in ['norte', 'sur']:
                raise ValueError(f"Hemisferio '{hemisphere}' no reconocido. Debe ser 'Norte' o 'Sur'.")
        except ValueError as e: # Catches int(zone_str) error too
            raise ValueError(f"Error en parámetros de zona/hemisferio: {e}")

        # Define transformation UTM -> WGS84
        # This can raise ProjError, which will propagate upwards
        epsg_from = 32600 + zone_int if hemisphere.lower() == "norte" else 32700 + zone_int
        transformer = Transformer.from_crs(f"EPSG:{epsg_from}", "EPSG:4326", always_xy=True)

        kml_root = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc = SubElement(kml_root, "Document")

        for feat in features:
            feat_id = feat.get("id", "SinID")
            geom_type = feat.get("type")
            coords = feat.get("coords")

            if not coords:
                print(f"Advertencia: Feature ID {feat_id} (tipo {geom_type}) no tiene coordenadas. Se omitirá.")
                continue

            pm = SubElement(doc, "Placemark")
            SubElement(pm, "name").text = str(feat_id)

            try:
                if isinstance(coords[0], (list, tuple)) and len(coords[0]) >= 2:
                    x0, y0 = coords[0][0], coords[0][1]
                    desc_text = (
                        f"Zona: {zone_str} ({hemisphere})\n"
                        f"Este: {x0:.2f} m\n"
                        f"Norte: {y0:.2f} m"
                    )
                    desc_elem = SubElement(pm, "description")
                    desc_elem.text = f"<![CDATA[{desc_text}]]>"
                else:
                    print(f"Advertencia: Formato de coordenadas[0] incorrecto para descripción en Feature ID {feat_id}. Descripción omitida.")
            except IndexError:
                print(f"Advertencia: Coordenadas vacías para descripción en Feature ID {feat_id}. Descripción omitida.")

            # Using GeometryType constants for robust comparison.
            if geom_type == GeometryType.PUNTO:
                if len(coords) != 1 or not isinstance(coords[0], (list, tuple)) or len(coords[0]) != 2:
                    print(f"Advertencia: Feature ID {feat_id} tipo {GeometryType.PUNTO} tiene formato de coordenadas inválido. Se omitirá geometría.")
                    doc.remove(pm) # Remove placemark if geometry is invalid
                    continue
                try:
                    lon, lat = transformer.transform(coords[0][0], coords[0][1])
                    geom_elem = SubElement(pm, "Point")
                    SubElement(geom_elem, "coordinates").text = f"{lon:.6f},{lat:.6f},0"
                except ProjError as pe:
                    print(f"Advertencia: Error de transformación para Feature ID {feat_id} ({GeometryType.PUNTO}): {pe}. Se omitirá geometría.")
                    doc.remove(pm)
                    continue

            elif geom_type == GeometryType.POLILINEA:
                if len(coords) < 2:
                    print(f"Advertencia: Feature ID {feat_id} tipo {GeometryType.POLILINEA} tiene menos de 2 coordenadas. Se omitirá geometría.")
                    doc.remove(pm)
                    continue
                geom_elem = SubElement(pm, "LineString")
                coords_text_list = []
                for coord_pair in coords:
                    if not isinstance(coord_pair, (list, tuple)) or len(coord_pair) != 2:
                        print(f"Advertencia: Par de coordenadas inválido {coord_pair} en Feature ID {feat_id} ({GeometryType.POLILINEA}). Se omitirá este par.")
                        continue
                    try:
                        lon, lat = transformer.transform(coord_pair[0], coord_pair[1])
                        coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                    except ProjError as pe:
                        print(f"Advertencia: Error de transformación para una coordenada en Feature ID {feat_id} ({GeometryType.POLILINEA}): {pe}. Se omitirá esta coordenada.")

                if len(coords_text_list) < 2:
                    print(f"Advertencia: No hay suficientes coordenadas válidas para Feature ID {feat_id} ({GeometryType.POLILINEA}) tras transformación/validación. Se omitirá geometría.")
                    doc.remove(pm)
                    continue
                SubElement(geom_elem, "coordinates").text = " ".join(coords_text_list)

            elif geom_type == GeometryType.POLIGONO:
                if len(coords) < 3:
                    print(f"Advertencia: Feature ID {feat_id} tipo {GeometryType.POLIGONO} tiene menos de 3 coordenadas. Se omitirá geometría.")
                    doc.remove(pm)
                    continue
                poly_elem = SubElement(pm, "Polygon")
                obb = SubElement(poly_elem, "outerBoundaryIs")
                lr = SubElement(obb, "LinearRing")
                coords_text_list = []
                current_ring = list(coords)
                if tuple(current_ring[0]) != tuple(current_ring[-1]):
                    current_ring.append(current_ring[0])

                for coord_pair in current_ring:
                    if not isinstance(coord_pair, (list, tuple)) or len(coord_pair) != 2:
                        print(f"Advertencia: Par de coordenadas inválido {coord_pair} en Feature ID {feat_id} ({GeometryType.POLIGONO}). Se omitirá este par.")
                        continue
                    try:
                        lon, lat = transformer.transform(coord_pair[0], coord_pair[1])
                        coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                    except ProjError as pe:
                        print(f"Advertencia: Error de transformación para una coordenada en Feature ID {feat_id} ({GeometryType.POLIGONO}): {pe}. Se omitirá esta coordenada.")

                if len(coords_text_list) < 4: # Anillo cerrado necesita al menos 4 puntos (3 unicos + cierre)
                    print(f"Advertencia: No hay suficientes coordenadas válidas para Feature ID {feat_id} ({GeometryType.POLIGONO}) tras transformación/validación. Se omitirá geometría.")
                    doc.remove(pm)
                    continue
                SubElement(lr, "coordinates").text = " ".join(coords_text_list)
            else:
                print(f"Advertencia: Tipo de geometría '{geom_type}' para Feature ID {feat_id} no soportado por KML (esperados: {GeometryType.PUNTO}, {GeometryType.POLILINEA}, {GeometryType.POLIGONO}). Se omitirá feature.")
                doc.remove(pm)
                continue

        return kml_root

    @staticmethod
    def export(features: list[dict],
               filename: str,
               hemisphere: str,
               zone: str):
        if not features:
            raise ValueError("No hay geometrías para exportar.")
        if not filename.lower().endswith(".kml"):
            raise ValueError("El nombre de archivo debe terminar en .kml")

        try:
            # Zona/hemisferio validation and transformer creation are now in _build_kml_root_element
            kml_root = KMLExporter._build_kml_root_element(features, hemisphere, zone)

            xml_bytes = tostring(kml_root, encoding="utf-8", method="xml")
            parsed_xml = minidom.parseString(xml_bytes)
            xml_str_pretty = parsed_xml.toprettyxml(indent="  ")

            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str_pretty)

        except (ValueError, ProjError) as e: # Catch specific errors from _build_kml_root_element
             raise RuntimeError(f"Error al preparar datos KML: {e}")
        except Exception as e: # Catch other potential errors during file writing etc.
            raise RuntimeError(f"Error al crear el archivo KML '{filename}': {e}")

# Ejemplo de uso (opcional, para testing directo)
if __name__ == '__main__':
    sample_features_ok = [
        {"id": 1, "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": 2, "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": 3, "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]}
    ]
    sample_features_mixed = [
        {"id": "ok_point", "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": "bad_transform_point", "type": "Punto", "coords": [(99999999.0, 4000000.0)]}, # Will cause ProjError
        {"id": "no_coords_point", "type": "Punto", "coords": None},
        {"id": "empty_coords_point", "type": "Punto", "coords": []},
        {"id": "bad_fmt_point", "type": "Punto", "coords": [(500000.0,)]},
        {"id": "ok_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": "bad_coord_in_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0,)]}, # bad pair
        {"id": "insufficient_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0)]},
        {"id": "no_coords_poly", "type": "Polígono", "coords": []},
        {"id": "invalid_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0)]}, # too few points
        {"id": "ok_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]},
        {"id": "unknown_type", "type": "Circulo", "coords": [(10.0,10.0)]}
    ]

    import os
    output_dir = "test_output_kml"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tests = [
        (sample_features_ok, "test_ok_refactored.kml", "Norte", "18", "OK"),
        (sample_features_mixed, "test_mixed_issues_refactored.kml", "Norte", "18", "OK (con advertencias)"),
        ([], "test_empty_features_refactored.kml", "Norte", "18", "ValueError"), # Caught by export()
        (sample_features_ok, "test_bad_zone_str_refactored.kml", "Norte", "XYZ", "RuntimeError"), # ValueError from _build_kml_root_element, caught as RuntimeError
        (sample_features_ok, "test_bad_zone_num_refactored.kml", "Norte", "99", "RuntimeError"), # ValueError from _build_kml_root_element
        (sample_features_ok, "test_bad_hemi_refactored.kml", "Este", "18", "RuntimeError"),    # ValueError from _build_kml_root_element
        (sample_features_ok, "test_bad_filename_refactored.kmz", "Norte", "18", "ValueError") # Caught by export()
    ]

    for features, filename, hemisphere, zone, expected_outcome in tests:
        full_path = os.path.join(output_dir, filename)
        print(f"\nIntentando exportar: {full_path} (Esperado: {expected_outcome})")
        try:
            KMLExporter.export(features, full_path, hemisphere, zone)
            print(f"Archivo {filename} generado exitosamente.")
        except (ValueError, RuntimeError) as e:
            print(f"Error ({expected_outcome} esperado para algunos tests): {e}")
