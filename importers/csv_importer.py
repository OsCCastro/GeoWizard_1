import csv
import os # Para el bloque de pruebas
# from core.coordinate_manager import GeometryType # Descomentar si se usan constantes de tipo

class CSVImporter:
    @staticmethod
    def import_file(filepath: str,
                    x_col_idx: int = 0,
                    y_col_idx: int = 1,
                    id_col_idx: int = None,
                    # type_col_idx: int = None, # Futura mejora: permitir tipo desde CSV
                    delimiter: str = ',',
                    skip_header: int = 0) -> list[dict]:
        """
        Importa coordenadas desde un archivo CSV, tratando cada fila como un feature de tipo Punto.

        Args:
            filepath: Ruta al archivo CSV.
            x_col_idx: Índice (base 0) de la columna para la coordenada X (Este).
            y_col_idx: Índice (base 0) de la columna para la coordenada Y (Norte).
            id_col_idx: Índice (base 0) opcional de la columna para el ID del feature.
            delimiter: Delimitador de columnas en el CSV.
            skip_header: Número de filas de encabezado a omitir.

        Returns:
            Una lista de diccionarios, donde cada diccionario representa un feature.

        Raises:
            FileNotFoundError: Si el archivo no se encuentra.
            RuntimeError: Para otros errores de importación.
        """

        features = []
        current_id_counter = 1 # Para generar IDs secuenciales si no se provee id_col_idx

        try:
            # Usar encoding='utf-8-sig' para manejar correctamente el BOM (Byte Order Mark)
            # que a veces añaden programas como Excel al guardar CSVs UTF-8.
            # newline='' es importante para el manejo correcto de finales de línea por el módulo csv
            with open(filepath, 'r', encoding='utf-8-sig', newline='') as csvfile:
                reader = csv.reader(csvfile, delimiter=delimiter)

                # Saltar filas de encabezado
                for i_skip in range(skip_header):
                    try:
                        next(reader)
                    except StopIteration:
                        print(f"Advertencia: Se intentó saltar {skip_header} filas de encabezado, pero el archivo tiene menos. No se leerán datos.")
                        return []

                # Procesar cada fila de datos
                for line_num, row in enumerate(reader, start=skip_header + 1): # line_num es el número de línea real en el archivo
                    if not row: # Omitir filas completamente vacías
                        print(f"Advertencia (Línea {line_num}): Fila vacía. Omitiendo.")
                        continue

                    try:
                        # Validar que las columnas X e Y existan y no estén vacías
                        if not (0 <= x_col_idx < len(row) and row[x_col_idx].strip()):
                            print(f"Advertencia (Línea {line_num}): Columna X ({x_col_idx}) fuera de rango o vacía. Omitiendo fila: {row}")
                            continue
                        if not (0 <= y_col_idx < len(row) and row[y_col_idx].strip()):
                            print(f"Advertencia (Línea {line_num}): Columna Y ({y_col_idx}) fuera de rango o vacía. Omitiendo fila: {row}")
                            continue

                        x_str = row[x_col_idx].strip()
                        y_str = row[y_col_idx].strip()

                        # Intentar convertir X e Y a float, manejando comas como separadores decimales
                        try:
                            x = float(x_str.replace(',', '.'))
                            y = float(y_str.replace(',', '.'))
                        except ValueError:
                            print(f"Advertencia (Línea {line_num}): Coordenadas X ('{x_str}') o Y ('{y_str}') no son numéricas válidas. Omitiendo fila.")
                            continue

                        # Manejar ID del feature
                        feature_id_val = None
                        if id_col_idx is not None:
                            if 0 <= id_col_idx < len(row) and row[id_col_idx].strip():
                                id_str = row[id_col_idx].strip()
                                try:
                                    feature_id_val = int(id_str)
                                except ValueError:
                                    print(f"Advertencia (Línea {line_num}): ID '{id_str}' no es un entero válido. Usando ID secuencial.")
                                    feature_id_val = current_id_counter
                                    current_id_counter += 1
                            else:
                                print(f"Advertencia (Línea {line_num}): Columna ID ({id_col_idx}) fuera de rango o vacía. Usando ID secuencial.")
                                feature_id_val = current_id_counter
                                current_id_counter += 1
                        else:
                            feature_id_val = current_id_counter
                            current_id_counter += 1

                        # Por ahora, todos los features importados son de tipo "Punto"
                        # geom_type = GeometryType.PUNTO
                        geom_type = "Punto" # Debe coincidir con GeometryType.PUNTO

                        features.append({
                            "id": feature_id_val,
                            "type": geom_type,
                            "coords": [(x, y)]
                        })

                    except IndexError:
                        print(f"Advertencia (Línea {line_num}): Fila con menos columnas de las esperadas. Omitiendo fila: {row}")
                        continue

        except FileNotFoundError:
            raise FileNotFoundError(f"Archivo no encontrado: {filepath}")
        except Exception as e:
            raise RuntimeError(f"Error al importar el archivo CSV '{filepath}': {e}")

        return features

if __name__ == '__main__':
    test_dir = "test_csv_imports"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)

    test_csv_path_basic = os.path.join(test_dir, "test_import_basic.csv")
    test_csv_path_errors = os.path.join(test_dir, "test_import_errors.csv")
    test_csv_path_custom_delim = os.path.join(test_dir, "test_import_custom.csv")
    test_csv_path_empty_rows = os.path.join(test_dir, "test_import_empty_rows.csv")
    test_csv_path_short_header = os.path.join(test_dir, "test_import_short_header.csv")

    test_csv_content_basic = """X,Y,ID
10.0,20.0,1
10.1,20.1,2
10.2,20.2,3""" # No newline at EOF

    test_csv_content_errors = """Este,Norte,Etiqueta
30,0,40,0,A
INVALID,40.1,B
30.2,INVALID,C
30.3,40.3
,30.5,D_emptyX
30.6,,E_emptyY
30.7,40.7,10.5
30.8,40.8,ID_OKAY"""

    test_csv_content_custom_delim = "X;Y;ID\n50.0;60.0;100\n50,1;60,1;101"
    test_csv_content_empty_rows = "X,Y,ID\n\n1.0,2.0,1\n\n\n3.0,4.0,2"
    test_csv_content_short_header = "X,Y,ID"

    with open(test_csv_path_basic, "w") as f: # Removed newline='' as content has it or not
        f.write(test_csv_content_basic)
    with open(test_csv_path_errors, "w") as f:
        f.write(test_csv_content_errors)
    with open(test_csv_path_custom_delim, "w") as f:
        f.write(test_csv_content_custom_delim)
    with open(test_csv_path_empty_rows, "w") as f:
        f.write(test_csv_content_empty_rows)
    with open(test_csv_path_short_header, "w") as f:
        f.write(test_csv_content_short_header)

    importer = CSVImporter()

    test_files_params = [
        (test_csv_path_basic, {'x_col_idx':0, 'y_col_idx':1, 'id_col_idx':2, 'skip_header':1}),
        (test_csv_path_errors, {'x_col_idx':0, 'y_col_idx':1, 'id_col_idx':2, 'skip_header':1}),
        (test_csv_path_custom_delim, {'x_col_idx':0, 'y_col_idx':1, 'id_col_idx':2, 'delimiter':';', 'skip_header':1}),
        (test_csv_path_empty_rows, {'x_col_idx':0, 'y_col_idx':1, 'id_col_idx':2, 'skip_header':1}),
        (test_csv_path_short_header, {'skip_header':2}),
        ("nonexistent.csv", {})
    ]

    for path, params in test_files_params:
        print(f"\n--- Importando {path} con params {params} ---")
        try:
            features = importer.import_file(path, **params)
            if features:
                for f_idx, f_val in enumerate(features): print(f"  Feature {f_idx}: {f_val}")
            else:
                print("  No features importados.")
        except Exception as e:
            print(f"  Error: {e}")

    # Considerar limpieza si se desea, pero omitido para inspección en este entorno.
    # import shutil
    # if os.path.exists(test_dir):
    #     shutil.rmtree(test_dir)
    #     print(f"\nDirectorio de prueba '{test_dir}' eliminado.")
