import fiona
from fiona.crs import from_epsg
from collections import OrderedDict, defaultdict
import os

# (Si se usaran constantes como GeometryType.PUNTO, se importarían aquí)
# from core.coordinate_manager import GeometryType

class ShapefileExporter:
    @staticmethod
    def export(features: list[dict], filename: str, hemisphere: str, zone: str):
        if not features:
            raise ValueError("No hay geometrías para exportar.")

        # No es necesario un try-except para ImportError aquí,
        # ya que gui.py lo maneja al llamar al exportador.
        # Si fiona no está, la importación al inicio del archivo fallará.

        try:
            zone_int = int(zone)
        except ValueError:
            raise ValueError(f"Zona UTM inválida: '{zone}'. Debe ser un número entero.")

        if hemisphere.lower() == 'norte':
            epsg_code = 32600 + zone_int
        elif hemisphere.lower() == 'sur':
            epsg_code = 32700 + zone_int
        else:
            raise ValueError(f"Hemisferio '{hemisphere}' no reconocido. Use 'Norte' o 'Sur'.")

        try:
            crs = from_epsg(epsg_code)
        except Exception as e: # from_epsg puede fallar por varias razones si el código es inválido
            raise ValueError(f"No se pudo generar el CRS para EPSG:{epsg_code}. Error: {e}")


        # Agrupar features por tipo de geometría fiona
        grouped_features = defaultdict(list)
        # Mapeo de tipos de geometría de la aplicación a tipos de fiona
        # Y también para asegurar que solo procesamos tipos que conocemos
        # Nota: Los tipos de geometría en `CoordinateManager` son "Punto", "Polilínea", "Polígono"
        geometry_type_map = {
            "Punto": "Point",          # Usado por CoordinateManager
            "Point": "Point",          # Por si acaso viniera en inglés
            "Polilínea": "LineString", # Usado por CoordinateManager
            "LineString": "LineString",
            "Polígono": "Polygon",     # Usado por CoordinateManager
            "Polygon": "Polygon"
        }

        for feat in features:
            app_geom_type = feat.get("type")
            fiona_geom_type = geometry_type_map.get(app_geom_type)

            if fiona_geom_type:
                grouped_features[fiona_geom_type].append(feat)
            else:
                print(f"Advertencia: Tipo de geometría '{app_geom_type}' para feature ID {feat.get('id', 'N/A')} no es soportado por ShapefileExporter y será omitido.")

        if not grouped_features:
            # Esto podría ocurrir si todos los features son de tipos no soportados
            raise ValueError("No hay geometrías con tipos soportados para exportar a Shapefile.")

        base_filename, _ = os.path.splitext(filename)
        exported_files_count = 0

        for fiona_geom_type, feats_in_group in grouped_features.items():
            # Construir nombre de archivo específico para este tipo de geometría
            # ej. si filename es "proyecto.shp", output_filename será "proyecto_point.shp"
            # Si el filename original no tiene extensión .shp, se añade.
            # Es más robusto si la GUI asegura que `filename` ya tiene la extensión deseada
            # o si el `base_filename` se deriva de `proj` en la GUI.
            # Aquí, asumimos que `filename` es el nombre base deseado por el usuario.

            # Si el filename original era "proyecto.shp", base_filename es "proyecto"
            # output_filename se convertirá en "proyecto_point.shp", etc.
            suffix = fiona_geom_type.lower()
            # Pluralizar de forma simple (points, linestrings, polygons)
            if suffix.endswith('y'):
                suffix = suffix[:-1] + 'ies'
            else:
                suffix = suffix + 's'
            output_filename = f"{base_filename}_{suffix}.shp"

            schema = {
                'geometry': fiona_geom_type,
                'properties': OrderedDict([('id', 'int')]) # Propiedad 'id' de tipo entero
            }

            try:
                with fiona.open(output_filename, 'w',
                                driver='ESRI Shapefile',
                                schema=schema,
                                crs=crs,
                                encoding='utf-8') as collection:

                    for feat_data in feats_in_group:
                        # Convertir coordenadas al formato GeoJSON-like que fiona espera
                        fiona_geometry_dict = None
                        raw_coords = feat_data.get('coords')

                        if not raw_coords:
                            print(f"Advertencia: Feature ID {feat_data.get('id', 'N/A')} tipo '{fiona_geom_type}' no tiene coordenadas. Se omitirá.")
                            continue

                        if fiona_geom_type == 'Point':
                            # Para Point, fiona espera una tupla (x, y)
                            if len(raw_coords) == 1 and len(raw_coords[0]) == 2:
                                fiona_geometry_dict = {'type': 'Point', 'coordinates': tuple(raw_coords[0])}
                            else:
                                print(f"Advertencia: Feature ID {feat_data.get('id', 'N/A')} tipo 'Point' tiene formato de coordenadas inválido. Se omitirá.")
                                continue

                        elif fiona_geom_type == 'LineString':
                            # Para LineString, fiona espera una lista de tuplas [(x1,y1), (x2,y2), ...]
                            if len(raw_coords) >= 2:
                                fiona_geometry_dict = {'type': 'LineString', 'coordinates': [tuple(c) for c in raw_coords]}
                            else:
                                print(f"Advertencia: Feature ID {feat_data.get('id', 'N/A')} tipo 'LineString' tiene menos de 2 coordenadas. Se omitirá.")
                                continue

                        elif fiona_geom_type == 'Polygon':
                            # Para Polygon, fiona espera una lista de anillos.
                            # Cada anillo es una lista de tuplas. El primer anillo es el exterior.
                            # El anillo debe estar cerrado (primer punto == último punto).
                            if len(raw_coords) >= 3:
                                closed_ring = raw_coords + [raw_coords[0]] if tuple(raw_coords[0]) != tuple(raw_coords[-1]) else raw_coords
                                fiona_geometry_dict = {'type': 'Polygon', 'coordinates': [[tuple(c) for c in closed_ring]]}
                            else:
                                print(f"Advertencia: Feature ID {feat_data.get('id', 'N/A')} tipo 'Polygon' tiene menos de 3 coordenadas. Se omitirá.")
                                continue

                        if fiona_geometry_dict:
                            collection.write({
                                'geometry': fiona_geometry_dict,
                                'properties': OrderedDict([('id', int(feat_data.get('id', 0)))]) # Asegurar que ID es int
                            })
                        # else: el feature fue omitido por formato inválido

                print(f"Archivo {output_filename} exportado exitosamente.")
                exported_files_count += 1

            except Exception as e:
                # Si un tipo de geometría falla, se informa y se intenta continuar con los otros.
                # Esto es mejor que fallar toda la exportación si, por ejemplo, solo los polígonos tienen un problema.
                print(f"Error al exportar el archivo Shapefile '{output_filename}': {e}")
                # Considerar acumular errores en una lista y mostrarlos al final o relanzar una excepción agrupada.

        if exported_files_count == 0:
            raise RuntimeError("No se pudo exportar ningún archivo Shapefile. Verifique los tipos de geometría y los datos.")

        # La GUI puede necesitar ser informada de los múltiples archivos creados.
        # Por ahora, el mensaje de éxito en gui.py es genérico.

# Ejemplo de uso (opcional, para testing directo)
if __name__ == '__main__':
    sample_features = [
        {"id": 1, "type": "Punto", "coords": [(500000.0, 4000000.0)]},
        {"id": "2", "type": "Punto", "coords": [(500050.0, 4000050.0)]}, # ID como string
        {"id": 3, "type": "Polilínea", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0), (500200.0, 4000000.0)]},
        {"id": 4, "type": "Polígono", "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0), (500050.0, 4000050.0)]}, # Polígono abierto
        {"id": 5, "type": "Polígono", "coords": [(600000.0, 4100000.0), (600100.0, 4100100.0), (600050.0, 4100050.0), (600000.0, 4100000.0)]}, # Polígono cerrado
        {"id": 6, "type": "Punto", "coords": []}, # Punto sin coordenadas
        {"id": 7, "type": "LíneaDesconocida", "coords": [(1,1),(2,2)]}, # Tipo desconocido
        {"id": 8, "type": "Polilínea", "coords": [(100,100)]}, # Polilínea inválida
    ]

    output_dir_shp = "test_output_shp"
    if not os.path.exists(output_dir_shp):
        os.makedirs(output_dir_shp)

    base_shp_filename = os.path.join(output_dir_shp, "test_export") # La GUI pasaría algo como "proyecto.shp"

    print(f"Intentando exportar a la base: {base_shp_filename}")
    try:
        ShapefileExporter.export(sample_features, base_shp_filename, "Norte", "18")
        print(f"Exportación Shapefile completada (ver directorio '{output_dir_shp}').")
    except (ValueError, RuntimeError, fiona.errors.FionaError) as e:
        print(f"Error durante la exportación Shapefile: {e}")
    except ImportError:
        print("Error: Fiona no está instalado. La exportación a Shapefile no es posible.")
