# exporters/kml_exporter.py
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from pyproj import Transformer

class KMLExporter:
    @staticmethod
    def export(features: list[dict],
               filename: str,
               hemisphere: str,
               zone: str):
        """
        features: lista de {id, type, coords:[(x,y),...]}
        hemisphere: "Norte" o "Sur"
        zone:      string con número de zona UTM, p.e. "14"
        """
        # 1) UTM -> WGS84
        z = int(zone)
        epsg_from = 32600 + z if hemisphere.lower()=="norte" else 32700 + z
        transformer = Transformer.from_crs(f"EPSG:{epsg_from}", "EPSG:4326", always_xy=True)

        # 2) Raíz KML
        kml = Element("kml", xmlns="http://www.opengis.net/kml/2.2")
        doc = SubElement(kml, "Document")

        for feat in features:
            pm = SubElement(doc, "Placemark")
            SubElement(pm, "name").text = str(feat["id"])

            # Descripción UTM
            x0, y0 = feat["coords"][0]
            desc = SubElement(pm, "description")
            cd = (
                f"Zona: {zone} ({hemisphere})\n"
                f"Este: {x0:.2f} m\n"
                f"Norte: {y0:.2f} m"
            )
            desc.text = f"<![CDATA[{cd}]]>"

            # Geometría
            if feat["type"] == "Point":
                geom = SubElement(pm, "Point")
                coords = feat["coords"]
                lon, lat = transformer.transform(*coords[0])
                SubElement(geom, "coordinates").text = f"{lon:.6f},{lat:.6f},0"

            elif feat["type"] == "LineString":
                geom = SubElement(pm, "LineString")
                coords_text = []
                for x,y in feat["coords"]:
                    lon, lat = transformer.transform(x, y)
                    coords_text.append(f"{lon:.6f},{lat:.6f},0")
                SubElement(geom, "coordinates").text = " ".join(coords_text)

            elif feat["type"] == "Polygon":
                poly = SubElement(pm, "Polygon")
                obb  = SubElement(poly, "outerBoundaryIs")
                lr   = SubElement(obb, "LinearRing")
                coords_text = []
                # cerramos el anillo: repetimos primer punto
                ring = feat["coords"] + [feat["coords"][0]]
                for x,y in ring:
                    lon, lat = transformer.transform(x, y)
                    coords_text.append(f"{lon:.6f},{lat:.6f},0")
                SubElement(lr, "coordinates").text = " ".join(coords_text)

        # 3) Escribir
        xmlstr = minidom.parseString(tostring(kml)).toprettyxml(indent="  ")
        with open(filename, "w", encoding="utf-8") as f:
            f.write(xmlstr)
