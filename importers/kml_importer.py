import xml.etree.ElementTree as ET
from pyproj import Transformer, ProjError
import os # Para el bloque de pruebas
import re


# from core.coordinate_manager import GeometryType # Para usar constantes de tipo GeometryType.PUNTO etc.

class KMLImporter:
    @staticmethod
    def _parse_coordinates(coord_string: str, geom_type_str_for_ring_check: str) -> list[tuple[float, float]]:
        """
        Parsea la cadena de coordenadas KML (ej. "lon,lat,alt lon,lat,alt ...").
        Devuelve una lista de tuplas (lon, lat), ignorando la altitud.
        Para Polígonos, elimina el último punto si es idéntico al primero.
        """
        points = []
        if not coord_string:
            return points

        raw_coord_parts = coord_string.strip().split() # Separa por espacios/newlines
        for part in raw_coord_parts:
            try:
                # Divide por coma y toma los dos primeros elementos (lon, lat)
                lon_str, lat_str, *_ = part.split(',')
                lon = float(lon_str)
                lat = float(lat_str)
                points.append((lon, lat))
            except ValueError:
                print(f"Advertencia: Coordenada KML malformada o no numérica '{part}' omitida.")
                continue

        # Para polígonos KML, el LinearRing usualmente está cerrado.
        # Se quita el último punto si es idéntico al primero para consistencia interna,
        # ya que la aplicación cierra los polígonos al exportar/visualizar si es necesario.
        # Usar los tipos de geometría de la aplicación ("Punto", "Polilínea", "Polígono")
        if geom_type_str_for_ring_check == "Polígono" and \
           len(points) > 1 and points[0] == points[-1]:
            points = points[:-1]
        return points

    @staticmethod
    def import_file(filepath: str, target_hemisphere: str, target_zone: int) -> list[dict]:
        """
        Importa geometrías desde un archivo KML, transformándolas al sistema UTM especificado.

        Args:
            filepath: Ruta al archivo KML.
            target_hemisphere: Hemisferio de destino ("Norte" o "Sur").
            target_zone: Zona UTM de destino (entero, 1-60).

        Returns:
            Una lista de diccionarios de features.

        Raises:
            FileNotFoundError: Si el archivo KML no se encuentra.
            RuntimeError: Para errores de parseo KML, transformación de coordenadas, u otros.
            ValueError: Para parámetros de zona/hemisferio inválidos.
        """
        features = []
        sequential_id_counter = 1

        try:
            zone_int = int(target_zone) # Asegurar que target_zone sea int
            if not (1 <= zone_int <= 60):
                raise ValueError(f"Zona UTM '{target_zone}' inválida. Debe estar entre 1 y 60.")
            if target_hemisphere.lower() not in ['norte', 'sur']:
                raise ValueError(f"Hemisferio '{target_hemisphere}' no reconocido. Debe ser 'Norte' o 'Sur'.")

            target_epsg = 32600 + zone_int if target_hemisphere.lower() == 'norte' else 32700 + zone_int
            transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{target_epsg}", always_xy=True)
        except ValueError as e:
            raise e
        except ProjError as e:
            raise RuntimeError(f"Error al inicializar el transformador de coordenadas para zona {target_zone}{target_hemisphere}: {e}")

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            root_tag = root.tag
            ns_uri_match = re.match(r'\{(.*)\}kml', root_tag)
            ns_uri = ns_uri_match.group(1) if ns_uri_match else ''
            ns = {'kml': ns_uri} if ns_uri else {} # Diccionario de namespace vacío si no hay namespace

            # Función auxiliar para encontrar elementos con o sin namespace
            def find_element(parent, tag, namespace_dict):
                if namespace_dict and namespace_dict.get('kml'): # Si hay un namespace kml definido
                    return parent.find(f"kml:{tag}", namespace_dict)
                return parent.find(tag) # Buscar sin namespace

            def findall_elements(parent, tag, namespace_dict):
                if namespace_dict and namespace_dict.get('kml'):
                    return parent.findall(f".//kml:{tag}", namespace_dict) # .// para búsqueda global
                return parent.findall(f".//{tag}")


            for placemark_elem in findall_elements(root, 'Placemark', ns):
                feature_id_text_elem = find_element(placemark_elem, 'name', ns)
                feature_id_text = feature_id_text_elem.text if feature_id_text_elem is not None else None

                feature_id = sequential_id_counter
                if feature_id_text and feature_id_text.strip():
                    try:
                        feature_id = int(feature_id_text.strip())
                    except ValueError:
                        print(f"Advertencia: Nombre de Placemark '{feature_id_text}' no es un entero. Usando ID secuencial {sequential_id_counter}.")
                sequential_id_counter += 1

                geom_node = None
                app_geom_type = None

                node_options_map = {
                    "Point": "Punto",
                    "LineString": "Polilínea",
                    "Polygon": "Polígono"
                }

                for kml_type, app_type in node_options_map.items():
                    node = find_element(placemark_elem, kml_type, ns)
                    if node is not None:
                        geom_node = node
                        app_geom_type = app_type
                        break

                if geom_node is None or app_geom_type is None:
                    print(f"Advertencia: Placemark ID {feature_id} no contiene geometría KML soportada. Omitiendo.")
                    continue

                coord_text_node = None
                if app_geom_type == "Polígono":
                    outer_boundary = find_element(geom_node, 'outerBoundaryIs', ns)
                    if outer_boundary is not None:
                        linear_ring = find_element(outer_boundary, 'LinearRing', ns)
                        if linear_ring is not None:
                            coord_text_node = find_element(linear_ring, 'coordinates', ns)
                else:
                    coord_text_node = find_element(geom_node, 'coordinates', ns)

                if coord_text_node is None or coord_text_node.text is None:
                    print(f"Advertencia: Geometría en Placemark ID {feature_id} no tiene etiqueta <coordinates> o está vacía. Omitiendo.")
                    continue

                lon_lat_coords = KMLImporter._parse_coordinates(coord_text_node.text, app_geom_type)

                if not lon_lat_coords:
                    print(f"Advertencia: No se pudieron parsear coordenadas para Placemark ID {feature_id}. Omitiendo.")
                    continue

                transformed_coords_utm = []
                valid_geometry_after_transform = True
                for lon, lat in lon_lat_coords:
                    try:
                        utm_x, utm_y = transformer.transform(lon, lat)
                        transformed_coords_utm.append((utm_x, utm_y))
                    except ProjError as pe:
                        print(f"Advertencia: Error al transformar coordenada ({lon},{lat}) para Placemark ID {feature_id}. Error: {pe}. Omitiendo feature completo.")
                        valid_geometry_after_transform = False
                        break

                if not valid_geometry_after_transform or not transformed_coords_utm:
                    continue

                if app_geom_type == "Punto" and len(transformed_coords_utm) != 1:
                    print(f"Advertencia: Feature Punto ID {feature_id} no resultó en 1 coordenada. Omitiendo.")
                    continue
                elif app_geom_type == "Polilínea" and len(transformed_coords_utm) < 2:
                    print(f"Advertencia: Feature Polilínea ID {feature_id} resultó en <2 coordenadas. Omitiendo.")
                    continue
                elif app_geom_type == "Polígono" and len(transformed_coords_utm) < 3: # 3 puntos base para un polígono
                    print(f"Advertencia: Feature Polígono ID {feature_id} resultó en <3 coordenadas base. Omitiendo.")
                    continue

                features.append({
                    "id": feature_id,
                    "type": app_geom_type,
                    "coords": transformed_coords_utm
                })

        except ET.ParseError as e:
            raise RuntimeError(f"Error al parsear el archivo KML: {filepath}. Archivo malformado o no es KML. Detalle: {e}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Archivo no encontrado: {filepath}")
        except Exception as e:
            raise RuntimeError(f"Error inesperado al importar el archivo KML '{filepath}': {e}")

        return features

if __name__ == '__main__':
    test_dir_kml = "test_kml_imports"
    if not os.path.exists(test_dir_kml):
        os.makedirs(test_dir_kml)

    test_kml_file = os.path.join(test_dir_kml, "test_import.kml")
    test_kml_file_no_ns = os.path.join(test_dir_kml, "test_import_no_ns.kml")

    test_kml_content = """<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <Placemark>
      <name>Punto de Prueba</name>
      <Point>
        <coordinates>-70.64827, -33.45694, 0</coordinates> <!-- Santiago, Chile -->
      </Point>
    </Placemark>
    <Placemark>
      <name>Linea de Prueba</name>
      <LineString>
        <coordinates>
          -70.65, -33.45, 0
          -70.60, -33.42, 0
          -70.55, -33.40, 0
        </coordinates>
      </LineString>
    </Placemark>
    <Placemark>
      <name>Poligono de Prueba (Cerrado)</name>
      <Polygon>
        <outerBoundaryIs>
          <LinearRing>
            <coordinates>
              -70.65, -33.50, 0
              -70.60, -33.50, 0
              -70.60, -33.55, 0
              -70.65, -33.55, 0
              -70.65, -33.50, 0
            </coordinates>
          </LinearRing>
        </outerBoundaryIs>
      </Polygon>
    </Placemark>
    <Placemark>
      <name>2</name> <!-- ID numérico -->
      <Point><coordinates>-71.0, -34.0, 0</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Punto Malformado</name>
      <Point><coordinates>lon,lat,alt</coordinates></Point>
    </Placemark>
    <Placemark>
      <name>Poligono Invalido (Pocos Puntos)</name>
      <Polygon><outerBoundaryIs><LinearRing><coordinates>-70, -33, 0 -70, -33, 0</coordinates></LinearRing></outerBoundaryIs></Polygon>
    </Placemark>
  </Document>
</kml>
"""
    # KML sin namespace explícito en el tag <kml>
    test_kml_content_no_ns = """<?xml version="1.0" encoding="UTF-8"?>
<kml>
  <Document>
    <Placemark>
      <name>Punto NoNS</name>
      <Point>
        <coordinates>-70.5, -33.5, 0</coordinates>
      </Point>
    </Placemark>
  </Document>
</kml>
"""
    with open(test_kml_file, "w", encoding='utf-8') as f:
        f.write(test_kml_content)
    with open(test_kml_file_no_ns, "w", encoding='utf-8') as f:
        f.write(test_kml_content_no_ns)

    importer = KMLImporter()

    print(f"--- Importando {test_kml_file} (a Zona 19S) ---")
    try:
        feats = importer.import_file(test_kml_file, target_hemisphere='Sur', target_zone=19)
        for f_idx, f_val in enumerate(feats):
            print(f"  Feature {f_idx}: ID={f_val['id']}, Tipo={f_val['type']}, Coords UTM Count={len(f_val['coords'])}")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\n--- Importando {test_kml_file_no_ns} (sin namespace en root, a Zona 19S) ---")
    try:
        feats_no_ns = importer.import_file(test_kml_file_no_ns, target_hemisphere='Sur', target_zone=19)
        for f_idx, f_val in enumerate(feats_no_ns):
            print(f"  Feature {f_idx}: ID={f_val['id']}, Tipo={f_val['type']}, Coords UTM Count={len(f_val['coords'])}")
    except Exception as e:
        print(f"  Error: {e}")

    print(f"\n--- Probando con zona inválida ---")
    try:
        importer.import_file(test_kml_file, target_hemisphere='Sur', target_zone=99)
    except Exception as e:
        print(f"  Error (esperado): {e}")

    # Considerar limpieza
    # import shutil
    # if os.path.exists(test_dir_kml):
    #    shutil.rmtree(test_dir_kml)
    #    print(f"\nDirectorio de prueba '{test_dir_kml}' eliminado.")
