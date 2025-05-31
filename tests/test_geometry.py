import unittest
from unittest.mock import MagicMock, patch

# Mock Qt classes before they are imported by the module we are testing
# This is important if running tests in an environment without a display server
# or full Qt installation.
mock_qpointf = MagicMock()
mock_qpainterpath = MagicMock()
mock_qpen = MagicMock()
mock_qt = MagicMock()

# Apply patches globally for the test module
# Note: These mocks are very basic. For complex Qt interactions, more detailed mocks
# or a test environment with Qt (like pytest-qt) would be needed.
# Here, we mostly care about the logic within GeometryBuilder, not Qt rendering.

# Modules to patch. We need to patch them where they are looked up,
# which is in 'PySide6.QtCore' and 'PySide6.QtGui'
qt_core_patch_dict = {
    'QPointF': mock_qpointf,
    'Qt': mock_qt,
}
qt_gui_patch_dict = {
    'QPainterPath': mock_qpainterpath,
    'QPen': mock_qpen,
}

# The module 'core.geometry' imports QPainterPath from PySide6.QtGui and QPointF from PySide6.QtCore
# So we need to patch those locations.
# We also need to patch QPen and Qt from PySide6.QtGui and PySide6.QtCore respectively for the same reason.

# We will use @patch decorators in the test methods or class for more targeted mocking.

from PySide6.QtCore import QPointF, Qt # These will be mocked if test is run standalone before patching
from PySide6.QtGui import QPainterPath, QPen # Same as above

from core.geometry import GeometryBuilder
from core.coordinate_manager import GeometryType

class TestGeometryBuilder(unittest.TestCase):

    def setUp(self):
        # Reset mocks for each test to ensure independence
        mock_qpointf.reset_mock()
        mock_qpainterpath.reset_mock()
        mock_qpen.reset_mock()
        mock_qt.reset_mock()

        # Configure the mock QPainterPath to behave minimally as needed
        self.mock_path_instance = MagicMock(spec=QPainterPath)
        mock_qpainterpath.return_value = self.mock_path_instance

        # Configure the mock QPen
        self.mock_pen_instance = MagicMock(spec=QPen)
        mock_qpen.return_value = self.mock_pen_instance


    @patch('core.geometry.QPen', new=mock_qpen)
    @patch('core.geometry.QPainterPath', new=mock_qpainterpath)
    @patch('core.geometry.QPointF', new=mock_qpointf)
    @patch('core.geometry.Qt', new=mock_qt)
    def test_paths_from_features_point(self):
        features = [
            {"id": 1, "type": GeometryType.PUNTO, "coords": [(10.0, 20.0)]}
        ]
        result = GeometryBuilder.paths_from_features(features)
        self.assertEqual(len(result), 0, "Point features should be skipped and not return a path/pen.")
        mock_qpainterpath.assert_not_called() # No QPainterPath should be created for points

    @patch('core.geometry.QPen', new=mock_qpen)
    @patch('core.geometry.QPainterPath', new=mock_qpainterpath)
    @patch('core.geometry.QPointF', new=mock_qpointf)
    @patch('core.geometry.Qt', new=mock_qt)
    def test_paths_from_features_polyline(self):
        mock_qt.blue = Qt.blue # Ensure mock_qt.blue is something comparable

        features = [
            {"id": 2, "type": GeometryType.POLILINEA, "coords": [(10.0, 20.0), (30.0, 40.0)]}
        ]
        result = GeometryBuilder.paths_from_features(features)

        self.assertEqual(len(result), 1, "Polyline should generate one path/pen tuple.")
        path_obj, pen_obj = result[0]

        self.assertEqual(path_obj, self.mock_path_instance)
        self.assertEqual(pen_obj, self.mock_pen_instance)

        # Check QPainterPath calls
        mock_qpointf.assert_any_call(10.0, 20.0) # Called for path start
        self.mock_path_instance.lineTo.assert_called_once_with(mock_qpointf(30.0,40.0))

        # Check QPen calls
        # We are checking against the mocked Qt.blue
        mock_qpen.assert_called_once_with(mock_qt.blue, 2)


    @patch('core.geometry.QPen', new=mock_qpen)
    @patch('core.geometry.QPainterPath', new=mock_qpainterpath)
    @patch('core.geometry.QPointF', new=mock_qpointf)
    @patch('core.geometry.Qt', new=mock_qt)
    def test_paths_from_features_polygon(self):
        mock_qt.green = Qt.green
        mock_qt.SolidLine = Qt.SolidLine

        coords = [(10.0, 20.0), (30.0, 40.0), (50.0, 10.0)]
        features = [
            {"id": 3, "type": GeometryType.POLIGONO, "coords": coords}
        ]
        result = GeometryBuilder.paths_from_features(features)

        self.assertEqual(len(result), 1, "Polygon should generate one path/pen tuple.")
        path_obj, pen_obj = result[0]

        self.assertEqual(path_obj, self.mock_path_instance)
        self.assertEqual(pen_obj, self.mock_pen_instance)

        # Check QPainterPath calls for polygon (including closure)
        # Path starts with coords[0]
        mock_qpointf.assert_any_call(coords[0][0], coords[0][1])
        # lineTo for other points
        self.mock_path_instance.lineTo.assert_any_call(mock_qpointf(coords[1][0], coords[1][1]))
        self.mock_path_instance.lineTo.assert_any_call(mock_qpointf(coords[2][0], coords[2][1]))
        # lineTo for closing point (back to coords[0])
        self.mock_path_instance.lineTo.assert_any_call(mock_qpointf(coords[0][0], coords[0][1]))

        # Check QPen calls
        mock_qpen.assert_called_once_with(mock_qt.green, 1)
        self.mock_pen_instance.setStyle.assert_called_once_with(mock_qt.SolidLine)

    @patch('core.geometry.QPen', new=mock_qpen)
    @patch('core.geometry.QPainterPath', new=mock_qpainterpath)
    @patch('core.geometry.QPointF', new=mock_qpointf)
    @patch('core.geometry.Qt', new=mock_qt)
    def test_paths_from_features_empty_or_invalid(self):
        # Test with empty coordinates list
        features_empty = [
            {"id": 4, "type": GeometryType.POLILINEA, "coords": []}
        ]
        result_empty = GeometryBuilder.paths_from_features(features_empty)
        self.assertEqual(len(result_empty), 0)

        # Test with insufficient points for polyline
        features_insufficient_polyline = [
            {"id": 5, "type": GeometryType.POLILINEA, "coords": [(10.0, 20.0)]}
        ]
        result_insufficient_polyline = GeometryBuilder.paths_from_features(features_insufficient_polyline)
        self.assertEqual(len(result_insufficient_polyline), 0)

        # Test with insufficient points for polygon
        features_insufficient_polygon = [
            {"id": 6, "type": GeometryType.POLIGONO, "coords": [(10.0, 20.0), (30.0, 40.0)]}
        ]
        result_insufficient_polygon = GeometryBuilder.paths_from_features(features_insufficient_polygon)
        self.assertEqual(len(result_insufficient_polygon), 0)

if __name__ == '__main__':
    unittest.main()
