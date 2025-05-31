# core/geometry.py
from PySide6.QtGui import QPainterPath, QPen
from PySide6.QtCore import QPointF, Qt
from core.coordinate_manager import GeometryType # Import GeometryType

class GeometryBuilder:
    """
    Construye objetos de dibujo (QPainterPath) a partir
    de la lista de features que devuelve CoordinateManager.
    """

    @staticmethod
    def paths_from_features(features: list[dict]):
        """
        Devuelve lista de tuplas (path: QPainterPath, pen: QPen)
        para cada feature.
        """
        result = []
        # Imports for QPen and Qt moved to top-level of module

        for feat in features:
            original_pts = feat["coords"] # Keep original coordinates
            typ = feat["type"]

            path = None # Initialize path
            pen = None  # Initialize pen

            if typ == GeometryType.PUNTO:
                # En GUI se dibujan los puntos como elipses directamente.
                # No se crea QPainterPath para Puntos aquí por lo tanto.
                continue

            elif typ == GeometryType.POLILINEA:
                if not original_pts or len(original_pts) < 2:
                    # print(f"Advertencia: Polilínea ID {feat.get('id', 'N/A')} con menos de 2 puntos. Omitiendo.")
                    continue

                path = QPainterPath(QPointF(original_pts[0][0], original_pts[0][1]))
                for x,y in original_pts[1:]:
                    path.lineTo(QPointF(x,y))
                pen = QPen(Qt.blue, 2)

            elif typ == GeometryType.POLIGONO:
                if not original_pts or len(original_pts) < 3:
                    # print(f"Advertencia: Polígono ID {feat.get('id', 'N/A')} con menos de 3 puntos base. Omitiendo.")
                    continue

                # Copiar y cerrar anillo para polígono
                closed_pts = list(original_pts)
                if tuple(closed_pts[0]) != tuple(closed_pts[-1]):
                    closed_pts.append(closed_pts[0])

                # Un polígono cerrado visualmente necesita al menos 3 puntos únicos + punto de cierre
                # (total 4 puntos en la lista closed_pts si el primero y ultimo son iguales)
                if len(closed_pts) < 4:
                    # print(f"Advertencia: Polígono ID {feat.get('id', 'N/A')} con menos de 3 puntos únicos tras cierre. Omitiendo.")
                    continue

                path = QPainterPath(QPointF(closed_pts[0][0], closed_pts[0][1]))
                for x,y in closed_pts[1:]:
                    path.lineTo(QPointF(x,y))
                # path.closeSubpath() # QPainterPath.addPolygon also closes, lineTo sequence for polygon should be closed by data

                pen = QPen(Qt.green, 1)
                pen.setStyle(Qt.SolidLine)

            else:
                # Tipo desconocido, no debería ocurrir si viene de CoordinateManager
                # print(f"Advertencia: Tipo de geometría desconocido o no manejado en GeometryBuilder: {typ} para feature ID {feat.get('id', 'N/A')}")
                continue

            if path and pen: # Solo agregar si se creó un path y pen válidos
                result.append((path, pen))
            # elif path and not pen:
                # print(f"Advertencia: Path creado pero pen no definido para {typ} ID {feat.get('id', 'N/A')}")


        return result
