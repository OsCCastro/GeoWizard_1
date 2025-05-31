# core/coordinate_manager.py

class CoordinateManager:
    def __init__(self, hemisphere: str, zone: int):
        self.hemisphere = hemisphere
        self.zone       = zone
        # lista de features: cada uno es dict con { id, type, coords }
        self.features   = []

    def add_feature(self, fid: int, geom_type: str, coords: list[tuple[float,float]]):
        """
        geom_type: "Punto", "Polilínea" o "Polígono"
        coords: [(x1,y1), (x2,y2), ...]
        """
        # validar aquí si quieres (UTM rango, números, etc.)
        self.features.append({
            "id":   fid,
            "type": geom_type,
            "coords": coords
        })

    def clear(self):
        self.features.clear()

    def get_features(self):
        return self.features
