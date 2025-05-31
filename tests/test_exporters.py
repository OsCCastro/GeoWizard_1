import unittest
from unittest.mock import patch, MagicMock
from xml.etree.ElementTree import Element, SubElement # Added SubElement
import zipfile
import io
import os # Added os for tearDown

from exporters.kml_exporter import KMLExporter
from exporters.kmz_exporter import KMZExporter
from core.coordinate_manager import GeometryType
from pyproj import ProjError # To test catching this exception

class TestKMLExporterSharedLogic(unittest.TestCase):
    """
    Tests for the shared KML building logic KMLExporter._build_kml_root_element.
    """

    def setUp(self):
        self.sample_features_point = [
            {"id": 1, "type": GeometryType.PUNTO, "coords": [(500000.0, 4000000.0)]}
        ]
        self.sample_features_linestring = [
            {"id": 2, "type": GeometryType.POLILINEA, "coords": [(500000.0, 4000000.0), (500100.0, 4000100.0)]}
        ]
        self.sample_features_polygon = [
            {"id": 3, "type": GeometryType.POLIGONO, "coords": [(500000.0, 4000000.0), (500100.0, 4000000.0), (500050.0, 4000100.0)]}
        ]
        self.hemisphere = "Norte"
        self.zone = "18" # String, as expected by the method

    @patch('exporters.kml_exporter.Transformer')
    def test_build_kml_point(self, MockTransformerClass):
        # Configure the mock transformer
        mock_transformer_instance = MagicMock() # spec=pyproj.Transformer if pyproj was directly imported here
        MockTransformerClass.from_crs.return_value = mock_transformer_instance
        # Simulate lon, lat for WGS84
        mock_transformer_instance.transform.return_value = (-70.0, -30.0)

        kml_root = KMLExporter._build_kml_root_element(self.sample_features_point, self.hemisphere, self.zone)
        self.assertIsInstance(kml_root, Element)
        # Assuming .tag might not include the full URI by default with this ElementTree setup
        self.assertEqual(kml_root.tag, "kml")
        self.assertEqual(kml_root.get("xmlns"), "http://www.opengis.net/kml/2.2") # Check namespace attribute

        doc = kml_root.find("Document") # Find without namespace prefix
        self.assertIsNotNone(doc)

        placemark = doc.find("Placemark") # Find without namespace prefix
        self.assertIsNotNone(placemark)

        name = placemark.findtext("name") # Find without namespace prefix
        self.assertEqual(name, "1")

        point_geom = placemark.find("Point") # Find without namespace prefix
        self.assertIsNotNone(point_geom)

        coordinates = point_geom.findtext("coordinates") # Find without namespace prefix
        self.assertEqual(coordinates, "-70.000000,-30.000000,0")
        mock_transformer_instance.transform.assert_called_once_with(500000.0, 4000000.0)

    @patch('exporters.kml_exporter.Transformer')
    def test_build_kml_linestring(self, MockTransformerClass):
        mock_transformer_instance = MagicMock()
        MockTransformerClass.from_crs.return_value = mock_transformer_instance
        mock_transformer_instance.transform.side_effect = [(-70.0, -30.0), (-70.01, -30.01)]

        kml_root = KMLExporter._build_kml_root_element(self.sample_features_linestring, self.hemisphere, self.zone)
        doc = kml_root.find("Document")
        self.assertIsNotNone(doc, "Document element should be found")
        placemark = doc.find("Placemark")
        self.assertIsNotNone(placemark, "Placemark element should be found")
        linestring_geom = placemark.find("LineString")
        self.assertIsNotNone(linestring_geom)
        coordinates = linestring_geom.findtext("coordinates")
        self.assertEqual(coordinates, "-70.000000,-30.000000,0 -70.010000,-30.010000,0")

    @patch('exporters.kml_exporter.Transformer')
    def test_build_kml_polygon(self, MockTransformerClass):
        mock_transformer_instance = MagicMock()
        MockTransformerClass.from_crs.return_value = mock_transformer_instance
        mock_transformer_instance.transform.side_effect = [
            (-70.0, -30.0), (-70.01, -30.0), (-70.005, -30.01), (-70.0, -30.0) # Closed
        ]
        kml_root = KMLExporter._build_kml_root_element(self.sample_features_polygon, self.hemisphere, self.zone)
        doc = kml_root.find("Document")
        self.assertIsNotNone(doc, "Document element should be found")
        placemark = doc.find("Placemark")
        self.assertIsNotNone(placemark, "Placemark element should be found")
        polygon_geom = placemark.find("Polygon")
        self.assertIsNotNone(polygon_geom)
        # Use .// to find LinearRing anywhere under polygon_geom, without namespace for simplicity here
        linear_ring = polygon_geom.find(".//LinearRing")
        self.assertIsNotNone(linear_ring)
        coordinates = linear_ring.findtext("coordinates")
        self.assertEqual(coordinates, "-70.000000,-30.000000,0 -70.010000,-30.000000,0 -70.005000,-30.010000,0 -70.000000,-30.000000,0")

    @patch('exporters.kml_exporter.Transformer')
    def test_build_kml_proj_error_on_transform(self, MockTransformerClass):
        mock_transformer_instance = MagicMock()
        MockTransformerClass.from_crs.return_value = mock_transformer_instance
        mock_transformer_instance.transform.side_effect = ProjError("Mocked Transform error")

        # Expect print warning and skipping of the geometry.
        # The Placemark will be removed by the logic in _build_kml_root_element.
        with patch('builtins.print') as mock_print:
            kml_root = KMLExporter._build_kml_root_element(self.sample_features_point, self.hemisphere, self.zone)
            doc = kml_root.find("Document") # Find without namespace prefix
            self.assertIsNotNone(doc, "Document element should still be found even if all placemarks fail")
            placemark = doc.find("Placemark") # Attempt to find a placemark
            self.assertIsNone(placemark, "Placemark should be removed if transform fails.")
            mock_print.assert_called() # Check that a warning was printed

    def test_build_kml_invalid_zone_format(self):
        with self.assertRaisesRegex(ValueError, "Error en parámetros de zona/hemisferio"):
            KMLExporter._build_kml_root_element(self.sample_features_point, self.hemisphere, "XYZ")

    def test_build_kml_invalid_zone_number(self):
        with self.assertRaisesRegex(ValueError, "Error en parámetros de zona/hemisferio"):
            KMLExporter._build_kml_root_element(self.sample_features_point, self.hemisphere, "99")

    def test_build_kml_invalid_hemisphere(self):
        with self.assertRaisesRegex(ValueError, "Error en parámetros de zona/hemisferio"):
            KMLExporter._build_kml_root_element(self.sample_features_point, "UnknownHemi", self.zone)

    @patch('exporters.kml_exporter.Transformer.from_crs', side_effect=ProjError("CRS init error"))
    def test_build_kml_proj_error_on_transformer_init(self, mock_from_crs):
        with self.assertRaisesRegex(ProjError, "CRS init error"): # Expect ProjError to propagate
            KMLExporter._build_kml_root_element(self.sample_features_point, self.hemisphere, self.zone)


class TestKMZExporter(unittest.TestCase):
    def setUp(self):
        self.sample_features = [
            {"id": 1, "type": GeometryType.PUNTO, "coords": [(500000.0, 4000000.0)]}
        ]
        self.hemisphere = "Norte"
        self.zone = "18"
        self.filename = "test_output.kmz"

    @patch('exporters.kmz_exporter.KMLExporter._build_kml_root_element')
    def test_export_kmz_structure(self, mock_build_kml_root):
        # Configure the mock shared KML builder
        mock_kml_element = Element("{http://www.opengis.net/kml/2.2}kml")
        doc_element = SubElement(mock_kml_element, "{http://www.opengis.net/kml/2.2}Document")
        SubElement(doc_element, "{http://www.opengis.net/kml/2.2}name").text = "Test KML for KMZ"
        mock_build_kml_root.return_value = mock_kml_element

        kmz_buffer = io.BytesIO()

        # Mock the ZipFile instance and its methods for context management
        mock_zip_file_instance = MagicMock(spec=zipfile.ZipFile)
        mock_zip_file_instance.__enter__.return_value = mock_zip_file_instance
        mock_zip_file_instance.__exit__.return_value = None # Or MagicMock()

        # Patch the ZipFile constructor to return our mock instance
        with patch('zipfile.ZipFile', return_value=mock_zip_file_instance) as mock_zip_constructor:
            KMZExporter.export(self.sample_features, self.filename, self.hemisphere, self.zone)

        # Verify KMLExporter._build_kml_root_element was called
        mock_build_kml_root.assert_called_once_with(self.sample_features, self.hemisphere, self.zone)

        # Verify ZipFile constructor was called
        mock_zip_constructor.assert_called_once_with(self.filename, 'w', zipfile.ZIP_DEFLATED)

        # Verify writestr was called on the zipfile instance
        # The actual content written to writestr comes from minidom, which is complex to replicate here exactly
        # So, we check that writestr was called with 'doc.kml' and some string data.
        mock_zip_file_instance.writestr.assert_called_once()
        args, _ = mock_zip_file_instance.writestr.call_args
        self.assertEqual(args[0], 'doc.kml')
        # Adjust for potential namespace prefixes like ns0:
        kml_content_from_zip = args[1].decode('utf-8')
        self.assertRegex(kml_content_from_zip, r"<ns0:name>Test KML for KMZ</ns0:name>|<name>Test KML for KMZ</name>")
        self.assertTrue(kml_content_from_zip.startswith("<?xml"))

    def tearDown(self):
        # Clean up dummy file if any test creates it (though current test_export_kmz_structure uses BytesIO)
        if os.path.exists(self.filename):
            self.assertTrue(kml_content_in_zip.startswith("<?xml"))


    def tearDown(self):
        # Clean up dummy file if any test creates it (though current test_export_kmz_structure uses BytesIO)
        if os.path.exists(self.filename):
            os.remove(self.filename)

if __name__ == '__main__':
    # This allows running tests directly.
    # For a more robust solution, use 'python -m unittest discover tests' from project root.
    # Need to ensure paths are correct if running this file directly, especially for imports.
    # Assuming 'core' and 'exporters' are in PYTHONPATH or relative to this file's execution path.

    # Add project root to sys.path for direct execution if tests are in a subdir
    import sys
    import os
    # This is a common way to ensure modules are found when running a test file directly
    # Adjust as per your project structure
    # sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

    unittest.main()
