# exporters/kml_exporter.py
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pyproj import Transformer, ProjError # Import ProjError for specific exception handling

# Si se usaran constantes de GeometryType, se importarían aquí.
# from core.coordinate_manager import GeometryType

class KMLExporter:
    @staticmethod
    def export(features: list[dict],
               filename: str,
               hemisphere: str,
               zone: str):
        """
        Exporta features a un archivo KML.

        Args:
            features: Lista de features. Cada feature es un dict con {id, type, coords:[(x,y),...]}.
            filename: Nombre del archivo KML de salida.
            hemisphere: "Norte" o "Sur".
            zone: Número de zona UTM (string o int).

        Raises:
            ValueError: Si los parámetros de entrada son inválidos (features vacíos, zona/hemisferio incorrectos, nombre de archivo).
            RuntimeError: Si ocurre un error durante la generación o escritura del KML.
        """
        if not features:
            raise ValueError("No hay geometrías para exportar.")

        if not filename.lower().endswith(".kml"):
            raise ValueError("El nombre de archivo debe terminar en .kml")

        try:
            zone_int = int(zone)
            if not (1 <= zone_int <= 60):
                raise ValueError(f"Zona UTM '{zone}' inválida. Debe estar entre 1 y 60.")
            if hemisphere.lower() not in ['norte', 'sur']:
                raise ValueError(f"Hemisferio '{hemisphere}' no reconocido. Debe ser 'Norte' o 'Sur'.")
        except ValueError as e: # Captura el error de int(zone) también
            raise ValueError(f"Error en parámetros de zona/hemisferio: {e}")

        try:
            # 1) Definir transformación UTM -> WGS84
            epsg_from = 32600 + zone_int if hemisphere.lower() == "norte" else 32700 + zone_int
            transformer = Transformer.from_crs(f"EPSG:{epsg_from}", "EPSG:4326", always_xy=True)

            # 2) Raíz KML
            kml_root = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
            doc = SubElement(kml_root, "Document")

            for feat in features:
                feat_id = feat.get("id", "SinID")
                geom_type = feat.get("type")
                # Validaciones en CoordinateManager deberían asegurar que coords es una lista de tuplas numéricas.
                # Aquí chequeamos existencia y estructura mínima.
                coords = feat.get("coords")

                if not coords: # Si coords es None o lista vacía
                    print(f"Advertencia: Feature ID {feat_id} (tipo {geom_type}) no tiene coordenadas. Se omitirá.")
                    continue

                pm = SubElement(doc, "Placemark")
                SubElement(pm, "name").text = str(feat_id)

                # Descripción UTM (usando la primera coordenada)
                try:
                    # Asegurar que coords[0] existe y es una tupla/lista de al menos 2 elementos
                    if isinstance(coords[0], (list, tuple)) and len(coords[0]) >= 2:
                        x0, y0 = coords[0][0], coords[0][1]
                        desc_text = (
                            f"Zona: {zone} ({hemisphere})\n"
                            f"Este: {x0:.2f} m\n"
                            f"Norte: {y0:.2f} m"
                        )
                        desc_elem = SubElement(pm, "description")
                        desc_elem.text = f"<![CDATA[{desc_text}]]>"
                    else:
                        print(f"Advertencia: Formato de coordenadas[0] incorrecto para descripción en Feature ID {feat_id}. Descripción omitida.")
                except IndexError: # Si coords[0] no existe (aunque ya chequeamos 'if not coords')
                    print(f"Advertencia: Coordenadas vacías para descripción en Feature ID {feat_id}. Descripción omitida.")


                # Geometría
                # Usar constantes/enum aquí sería mejor (ej. GeometryType.PUNTO)
                # Los tipos de geometría deben coincidir con los definidos en GeometryType
                # en core.coordinate_manager (Punto, Polilínea, Polígono)
                if geom_type == "Punto": # o GeometryType.PUNTO
                    if len(coords) != 1 or not isinstance(coords[0], (list, tuple)) or len(coords[0]) != 2:
                        print(f"Advertencia: Feature ID {feat_id} tipo Punto tiene formato de coordenadas inválido. Se omitirá geometría.")
                        doc.remove(pm)
                        continue
                    try:
                        lon, lat = transformer.transform(coords[0][0], coords[0][1])
                        geom_elem = SubElement(pm, "Point")
                        SubElement(geom_elem, "coordinates").text = f"{lon:.6f},{lat:.6f},0"
                    except ProjError as pe:
                        print(f"Advertencia: Error de transformación para Feature ID {feat_id} (Punto): {pe}. Se omitirá geometría.")
                        doc.remove(pm)
                        continue

                elif geom_type == "Polilínea": # o GeometryType.POLILINEA
                    if len(coords) < 2:
                        print(f"Advertencia: Feature ID {feat_id} tipo Polilínea tiene menos de 2 coordenadas. Se omitirá geometría.")
                        doc.remove(pm)
                        continue

                    geom_elem = SubElement(pm, "LineString")
                    coords_text_list = []
                    for x,y_coord_pair in enumerate(coords): # Renombrar variable para claridad
                        if not isinstance(y_coord_pair, (list, tuple)) or len(y_coord_pair) != 2:
                             print(f"Advertencia: Par de coordenadas inválido {y_coord_pair} en Feature ID {feat_id} (Polilínea). Se omitirá este par.")
                             continue
                        try:
                            lon, lat = transformer.transform(y_coord_pair[0], y_coord_pair[1])
                            coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                        except ProjError as pe:
                            print(f"Advertencia: Error de transformación para una coordenada en Feature ID {feat_id} (Polilínea): {pe}. Se omitirá esta coordenada.")

                    if len(coords_text_list) < 2 :
                         print(f"Advertencia: No hay suficientes coordenadas válidas para Feature ID {feat_id} (Polilínea) tras transformación/validación. Se omitirá geometría.")
                         doc.remove(pm)
                         continue
                    SubElement(geom_elem, "coordinates").text = " ".join(coords_text_list)

                elif geom_type == "Polígono": # o GeometryType.POLIGONO
                    if len(coords) < 3:
                        print(f"Advertencia: Feature ID {feat_id} tipo Polígono tiene menos de 3 coordenadas. Se omitirá geometría.")
                        doc.remove(pm)
                        continue

                    poly_elem = SubElement(pm, "Polygon")
                    obb = SubElement(poly_elem, "outerBoundaryIs")
                    lr = SubElement(obb, "LinearRing")
                    coords_text_list = []

                    current_ring = list(coords)
                    if tuple(current_ring[0]) != tuple(current_ring[-1]): # Asegurar cierre del anillo
                        current_ring.append(current_ring[0])

                    for x,y_coord_pair in enumerate(current_ring): # Renombrar variable
                        if not isinstance(y_coord_pair, (list, tuple)) or len(y_coord_pair) != 2:
                             print(f"Advertencia: Par de coordenadas inválido {y_coord_pair} en Feature ID {feat_id} (Polígono). Se omitirá este par.")
                             continue
                        try:
                            lon, lat = transformer.transform(y_coord_pair[0], y_coord_pair[1])
                            coords_text_list.append(f"{lon:.6f},{lat:.6f},0")
                        except ProjError as pe:
                            print(f"Advertencia: Error de transformación para una coordenada en Feature ID {feat_id} (Polígono): {pe}. Se omitirá esta coordenada.")

                    if len(coords_text_list) < 4: # Un anillo cerrado necesita al menos 4 puntos (3 unicos + cierre)
                        print(f"Advertencia: No hay suficientes coordenadas válidas para Feature ID {feat_id} (Polígono) tras transformación/validación. Se omitirá geometría.")
                        doc.remove(pm)
                        continue
                    SubElement(lr, "coordinates").text = " ".join(coords_text_list)
                else:
                    print(f"Advertencia: Tipo de geometría '{geom_type}' para Feature ID {feat_id} no soportado por KML. Se omitirá feature.")
                    doc.remove(pm)
                    continue

            # 3) Escribir
            xml_bytes = tostring(kml_root, encoding="utf-8", method="xml")
            parsed_xml = minidom.parseString(xml_bytes)
            xml_str_pretty = parsed_xml.toprettyxml(indent="  ")

            with open(filename, "w", encoding="utf-8") as f:
                f.write(xml_str_pretty)

        except ProjError as pe_crs:
             raise RuntimeError(f"Error de proyección al definir el transformador CRS para EPSG:{epsg_from}: {pe_crs}")
        except Exception as e:
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
        {"id": "bad_transform_point", "type": "Punto", "coords": [(99999999.0, 4000000.0)]},
        {"id": "no_coords_point", "type": "Punto", "coords": None},
        {"id": "empty_coords_point", "type": "Punto", "coords": []},
        {"id": "bad_fmt_point", "type": "Punto", "coords": [(500000.0,)]},
        {"id": "ok_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]},
        {"id": "bad_coord_in_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0,)]},
        {"id": "insufficient_line", "type": "Polilínea", "coords": [(500000.0, 4000000.0)]},
        {"id": "no_coords_poly", "type": "Polígono", "coords": []},
        {"id": "invalid_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0)]},
        {"id": "ok_poly", "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]},
        {"id": "unknown_type", "type": "Circulo", "coords": [(10.0,10.0)]}
    ]

    import os
    output_dir = "test_output_kml"
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    tests = [
        (sample_features_ok, "test_ok.kml", "Norte", "18", "OK"),
        (sample_features_mixed, "test_mixed_issues.kml", "Norte", "18", "OK (con advertencias)"),
        ([], "test_empty_features.kml", "Norte", "18", "ValueError"),
        (sample_features_ok, "test_bad_zone_str.kml", "Norte", "XYZ", "ValueError"),
        (sample_features_ok, "test_bad_zone_num.kml", "Norte", "99", "ValueError"),
        (sample_features_ok, "test_bad_hemi.kml", "Este", "18", "ValueError"),
        (sample_features_ok, "test_bad_filename.kmz", "Norte", "18", "ValueError") # Prueba de nombre de archivo
    ]

    for features, filename, hemisphere, zone, expected_outcome in tests:
        full_path = os.path.join(output_dir, filename)
        print(f"\nIntentando exportar: {full_path} (Esperado: {expected_outcome})")
        try:
            KMLExporter.export(features, full_path, hemisphere, zone)
            print(f"Archivo {filename} generado exitosamente.")
        except (ValueError, RuntimeError) as e:
            print(f"Error ({expected_outcome} esperado para algunos tests): {e}")
