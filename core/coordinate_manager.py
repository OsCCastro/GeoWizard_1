# core/coordinate_manager.py

class GeometryType:
    PUNTO = "Punto"
    POLILINEA = "Polilínea"
    POLIGONO = "Polígono"
    VALID_TYPES = [PUNTO, POLILINEA, POLIGONO]

class CoordinateManager:
    def __init__(self, hemisphere: str, zone: int):
        self.hemisphere = hemisphere
        self.zone       = zone
        # lista de features: cada uno es dict con { id, type, coords }
        self.features   = []

    def add_feature(self, fid: int, geom_type: str, coords: list[tuple[float,float]]):
        """
        Añade un feature a la lista, validando los datos de entrada.

        Args:
            fid: ID del feature.
            geom_type: Tipo de geometría ("Punto", "Polilínea", "Polígono").
            coords: Lista de tuplas de coordenadas [(x1,y1), (x2,y2), ...].

        Raises:
            ValueError: Si el tipo de geometría no es válido, o si la estructura
                        de coordenadas no coincide con el tipo de geometría,
                        o si los valores de coordenadas no son numéricos.
            TypeError: Si 'coords' no es una lista, o si algún elemento de 'coords'
                       no es una tupla/lista.
        """
        # Validación del tipo de geometría
        if geom_type not in GeometryType.VALID_TYPES:
            raise ValueError(
                f"Tipo de geometría '{geom_type}' no válido. Válidos son: {GeometryType.VALID_TYPES}"
            )

        # Validación del tipo de 'coords'
        if not isinstance(coords, list):
            raise TypeError("Las coordenadas deben ser una lista.")

        # Validación de lista de coordenadas no vacía
        if not coords:
            raise ValueError("La lista de coordenadas no puede estar vacía.")

        # Validación de cada elemento en 'coords'
        for i, coord_tuple in enumerate(coords):
            if not isinstance(coord_tuple, (list, tuple)):
                raise TypeError(
                    f"Cada coordenada debe ser una tupla o lista. Elemento {i} es de tipo: {type(coord_tuple)}"
                )
            if len(coord_tuple) != 2:
                raise ValueError(
                    f"Cada tupla de coordenada debe tener exactamente dos elementos (X, Y). Elemento {i} tiene: {len(coord_tuple)} elementos."
                )
            if not all(isinstance(val, (int, float)) for val in coord_tuple):
                raise ValueError(
                    f"Los valores de las coordenadas X e Y deben ser numéricos (int o float). Elemento {i} tiene valores: {coord_tuple}"
                )

        # Validación de la estructura de 'coords' según 'geom_type'
        if geom_type == GeometryType.PUNTO:
            if len(coords) != 1:
                raise ValueError(f"Geometría '{GeometryType.PUNTO}' debe tener exactamente 1 coordenada. Se encontraron: {len(coords)}")
        elif geom_type == GeometryType.POLILINEA:
            if len(coords) < 2:
                raise ValueError(
                    f"Geometría '{GeometryType.POLILINEA}' debe tener al menos 2 coordenadas. Se encontraron: {len(coords)}"
                )
        elif geom_type == GeometryType.POLIGONO:
            if len(coords) < 3:
                raise ValueError(
                    f"Geometría '{GeometryType.POLIGONO}' debe tener al menos 3 coordenadas base (sin cierre explícito aquí). Se encontraron: {len(coords)}"
                )

        # Si todas las validaciones pasan
        self.features.append({
            "id":   fid,
            "type": geom_type,
            "coords": coords
        })

    def clear(self):
        self.features.clear()

    def get_features(self):
        return self.features
