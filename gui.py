import os
import re
import math # Importar math
from PySide6.QtCore import Qt, QRegularExpression, QPointF, QItemSelectionModel
from PySide6.QtGui import (
    QAction,
    QRegularExpressionValidator,
    QBrush,
    QPainterPath,
    QPen,
    QResizeEvent
)
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QToolBar,
    QStyle,
    QMessageBox,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QLineEdit,
    QPushButton,
    QLabel,
    QFileDialog,
    QCheckBox,
    QGraphicsView,
    QGraphicsScene,
    QHeaderView,
    QMenu,
    QStyledItemDelegate,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser
)

from config_dialog import ConfigDialog
from help_dialog import HelpDialog
from core.coordinate_manager import CoordinateManager, GeometryType
from exporters.kml_exporter import KMLExporter
from exporters.kmz_exporter import KMZExporter
from exporters.shapefile_exporter import ShapefileExporter
from importers.csv_importer import CSVImporter
from importers.kml_importer import KMLImporter
from core.geometry import GeometryBuilder


class UTMDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        rx = QRegularExpression(r'^\d{6,7}(\.\d+)?$')
        editor.setValidator(QRegularExpressionValidator(rx, editor))
        return editor

    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, text)
        color = Qt.black if editor.hasAcceptableInput() else Qt.red
        model.setData(index, QBrush(color), Qt.ForegroundRole)

class CoordTable(QTableWidget):
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Tab and self.currentColumn() == 2:
            self.setCurrentCell(self.currentRow() + 1, 1)
            return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIG: Gestión de Coordenadas")
        self.generated_html_content = None # Inicializar
        self._build_ui()
        self._create_toolbar()

    # --- Métodos para overlays en Canvas ---
    def _show_canvas_error(self, message: str):
        if not hasattr(self, 'canvas_error_label'): return
        self.canvas_error_label.setText(message)
        self.canvas_error_label.adjustSize()
        self.canvas_error_label.show()
        self._position_canvas_widgets()
        self.canvas_error_label.raise_()

    def _clear_canvas_error(self):
        if not hasattr(self, 'canvas_error_label'): return
        self.canvas_error_label.hide()
        self.canvas_error_label.setText("")

    def _position_canvas_widgets(self):
        if hasattr(self, 'canvas_error_label') and self.canvas_error_label.isVisible():
            self.canvas_error_label.move(
                self.canvas.width() // 2 - self.canvas_error_label.width() // 2,
                self.canvas.height() - self.canvas_error_label.height() - 10
            )
            self.canvas_error_label.raise_() # Asegurar que esté encima

        if hasattr(self, 'html_preview_widget') and self.html_preview_widget.isVisible():
            preview_width = int(self.canvas.width() * 0.45)
            preview_height = int(self.canvas.height() * 0.35)
            preview_x = self.canvas.width() - preview_width - 5
            preview_y = self.canvas.height() - preview_height - 5
            self.html_preview_widget.setGeometry(preview_x, preview_y, preview_width, preview_height)
            self.html_preview_widget.raise_() # Asegurar que esté encima

    def resizeEvent(self, event: QResizeEvent):
        super().resizeEvent(event)
        self._position_canvas_widgets()

    # --- Métodos de UI ---
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        control_panel_widget = QWidget()
        control = QVBoxLayout(control_panel_widget)

        hz = QHBoxLayout()
        hz.addWidget(QLabel("Hemisferio:"))
        self.cb_hemisferio = QComboBox(); self.cb_hemisferio.addItems(["Norte","Sur"])
        hz.addWidget(self.cb_hemisferio)
        hz.addWidget(QLabel("Zona UTM:"))
        self.cb_zona = QComboBox(); self.cb_zona.addItems([str(i) for i in range(1,61)])
        hz.addWidget(self.cb_zona)
        control.addLayout(hz)

        self.table = CoordTable(1,3)
        self.table.setHorizontalHeaderLabels(["ID","X (Este)","Y (Norte)"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch); hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        first = QTableWidgetItem("1"); first.setFlags(Qt.ItemIsEnabled); self.table.setItem(0,0,first)
        delegate = UTMDelegate(self.table)
        self.table.setItemDelegateForColumn(1, delegate); self.table.setItemDelegateForColumn(2, delegate)
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)
        control.addWidget(self.table)

        geo = QHBoxLayout()
        geo.addWidget(QLabel("Geometría:"))
        self.chk_punto = QCheckBox("Punto"); self.chk_polilinea = QCheckBox("Polilínea"); self.chk_poligono = QCheckBox("Polígono")
        geo.addWidget(self.chk_punto); geo.addWidget(self.chk_polilinea); geo.addWidget(self.chk_poligono)
        control.addLayout(geo)

        options_layout = QHBoxLayout()
        self.chk_mapbase = QCheckBox("Usar mapa base (OSM)"); options_layout.addWidget(self.chk_mapbase)
        self.chk_show_html_table = QCheckBox("Mostrar Tabla HTML")
        self.chk_show_html_table.toggled.connect(self._on_toggle_html_table_preview)
        options_layout.addWidget(self.chk_show_html_table)
        options_layout.addStretch()
        control.addLayout(options_layout)

        ff = QHBoxLayout()
        ff.addWidget(QLabel("Proyecto:")); self.le_nombre = QLineEdit(); ff.addWidget(self.le_nombre)
        ff.addWidget(QLabel("Formato:")); self.cb_format = QComboBox(); self.cb_format.addItems([".kml",".kmz",".shp"]); ff.addWidget(self.cb_format)
        control.addLayout(ff)

        bl = QHBoxLayout(); bl.addStretch(); btn = QPushButton("Seleccionar carpeta"); btn.clicked.connect(self._on_guardar); bl.addWidget(btn)
        control.addLayout(bl)
        control.addStretch()

        self.canvas = QGraphicsView()
        self.scene  = QGraphicsScene(self.canvas); self.canvas.setScene(self.scene)
        self.canvas.setMinimumSize(400,300); self.canvas.setStyleSheet("background-color:white; border:1px solid #ccc; padding:0px;")

        self.canvas_error_label = QLabel(self.canvas)
        self.canvas_error_label.setStyleSheet("color: red; background-color: rgba(255, 255, 255, 210); padding: 5px; border: 1px solid red; border-radius: 3px;")
        self.canvas_error_label.hide()

        self.html_preview_widget = QTextBrowser(self.canvas)
        self.html_preview_widget.setStyleSheet("border: 1px solid grey; background-color: rgba(255, 255, 255, 230); font-family: monospace;")
        self.html_preview_widget.setReadOnly(True); self.html_preview_widget.hide()

        main_layout.addWidget(control_panel_widget, 1)
        main_layout.addWidget(self.canvas, 2)

    def _create_toolbar(self):
        tb = QToolBar("Principal"); self.addToolBar(tb)
        actions_data = [
            (QStyle.SP_FileIcon, "Nuevo", self._on_new),
            (QStyle.SP_DialogOpenButton, "Abrir", self._on_open),
            (QStyle.SP_DialogSaveButton, "Guardar", self._on_guardar),
            (QStyle.SP_DirOpenIcon, "Importar", self._on_import),
            (QStyle.SP_DialogSaveButton, "Exportar", self._on_export),
            None,
            (QStyle.SP_ArrowBack, "Deshacer", self._on_undo),
            (QStyle.SP_ArrowForward, "Rehacer", self._on_redo),
            None,
            (QStyle.SP_TitleBarMaxButton, "Mostrar/Ocultar lienzo", self.canvas.setVisible, True, True),
            (QStyle.SP_FileDialogListView, "Exportar HTML", self._on_generate_html_table),
            None,
            (QStyle.SP_DialogYesButton, "Modo oscuro", lambda ch: QApplication.instance().setStyleSheet("QWidget{background:#2b2b2b;color:#ddd;}" if ch else ""), True, False),
            None,
            (QStyle.SP_FileDialogDetailedView, "Configuraciones", self._on_settings),
            (QStyle.SP_DialogHelpButton, "Ayuda", self._on_help),
        ]
        for item_data in actions_data:
            if item_data is None: tb.addSeparator(); continue
            action = QAction(self.style().standardIcon(item_data[0]), item_data[1], self)
            action.triggered.connect(item_data[2])
            if len(item_data) > 3: action.setCheckable(item_data[3])
            if len(item_data) > 4: action.setChecked(item_data[4])
            tb.addAction(action)

    # --- Métodos de Cálculo Geométrico ---
    def _calculate_length(self, coords: list[tuple[float, float]]) -> float:
        length = 0.0
        if len(coords) < 2: return 0.0
        for i in range(len(coords) - 1):
            p1 = coords[i]
            p2 = coords[i+1]
            length += math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
        return length

    def _calculate_polygon_area(self, coords: list[tuple[float, float]]) -> float:
        if len(coords) < 3: return 0.0
        # Fórmula de Shoelace (Área de Gauss)
        area = 0.0
        n = len(coords)
        for i in range(n):
            j = (i + 1) % n
            area += coords[i][0] * coords[j][1]
            area -= coords[j][0] * coords[i][1]
        return math.fabs(area * 0.5)

    # --- Slots para HTML ---
    def _on_generate_html_table(self):
        self._clear_canvas_error()
        project_name = self.le_nombre.text().strip() or "MiProyecto"

        table_data = []
        for r in range(self.table.rowCount()):
            id_item = self.table.item(r, 0)
            x_item = self.table.item(r, 1)
            y_item = self.table.item(r, 2)
            if x_item and y_item and x_item.text().strip() and y_item.text().strip():
                try:
                    x_val = float(x_item.text())
                    y_val = float(y_item.text())
                    row_id = id_item.text().strip() if id_item else str(r + 1)
                    table_data.append((row_id, f"{x_val:.2f}", f"{y_val:.2f}"))
                except ValueError:
                    continue # Omitir filas con X,Y no numéricos

        if not table_data:
            QMessageBox.warning(self, "Tabla Vacía", "No hay datos válidos en la tabla para generar el HTML.")
            return

        mgr = self._build_manager_from_table()
        if mgr is None: return # Error de zona ya manejado

        perimetro_str = "N/A"
        area_str = "N/A"

        # Calcular perímetro y área basados en los features del manager (que respetan los checkboxes)
        active_features = mgr.get_features()
        if active_features:
            # Simplificación: Si hay una polilínea activa, se calcula su perímetro.
            # Si hay un polígono activo, se calcula su perímetro y área.
            # Si ambos están activos, se prioriza el polígono para el área, y el perímetro podría ser el del polígono.
            # O se podría reportar para el primer feature de cada tipo.
            # Para esta tarea, usaremos la primera polilínea y/o polígono encontrado.

            first_linestring_coords = None
            first_polygon_coords = None

            for feat in active_features:
                if feat["type"] == GeometryType.POLILINEA and not first_linestring_coords:
                    first_linestring_coords = feat["coords"]
                if feat["type"] == GeometryType.POLIGONO and not first_polygon_coords:
                    first_polygon_coords = feat["coords"]

            if first_polygon_coords: # Priorizar polígono para los cálculos
                # Perímetro del polígono (cerrando el anillo)
                poly_perimeter_coords = first_polygon_coords + [first_polygon_coords[0]]
                perimetro_val = self._calculate_length(poly_perimeter_coords)
                perimetro_str = f"{perimetro_val:.2f} m"

                area_val = self._calculate_polygon_area(first_polygon_coords) # Shoelace no necesita cierre explícito si se usa bien
                area_str = f"{area_val:.2f} m²"
            elif first_linestring_coords: # Si no hay polígono, pero sí polilínea
                perimetro_val = self._calculate_length(first_linestring_coords)
                perimetro_str = f"{perimetro_val:.2f} m (Polilínea)"
                area_str = "N/A (es Polilínea)"


        html = f"""
        <html><head><title>Reporte de Coordenadas - {project_name}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            table {{ border-collapse: collapse; width: 80%; margin: 20px auto; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
            th, td {{ border: 1px solid #ddd; padding: 10px; text-align: center; }}
            th {{ background-color: #f2f2f2; font-weight: bold; }}
            caption {{ font-size: 1.5em; margin: 10px; font-weight: bold; color: #333; }}
            .footer-info td {{ text-align: left; font-weight: bold; background-color: #f9f9f9; }}
        </style></head><body>
        <table>
            <caption>{project_name}</caption>
            <thead><tr><th>No.</th><th>X (Este)</th><th>Y (Norte)</th></tr></thead>
            <tbody>
        """
        for row in table_data:
            html += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>\n"
        html += f"""
            </tbody>
            <tfoot>
                <tr class="footer-info"><td colspan="3">Perímetro: {perimetro_str}</td></tr>
                <tr class="footer-info"><td colspan="3">Área: {area_str}</td></tr>
            </tfoot>
        </table></body></html>
        """
        self.generated_html_content = html

        # Guardar el archivo HTML
        save_path, _ = QFileDialog.getSaveFileName(self, "Guardar Tabla HTML", f"{project_name}.html", "HTML Files (*.html *.htm)")
        if save_path:
            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(self.generated_html_content)
                QMessageBox.information(self, "HTML Generado", f"Tabla HTML guardada en:\n{save_path}")
            except Exception as e:
                QMessageBox.critical(self, "Error al Guardar HTML", f"No se pudo guardar el archivo HTML:\n{e}")

        self._update_html_preview()


    def _update_html_preview(self):
        if self.chk_show_html_table.isChecked() and self.generated_html_content:
            self.html_preview_widget.setHtml(self.generated_html_content)
            self.html_preview_widget.show()
        else:
            self.html_preview_widget.hide()
        self._position_canvas_widgets() # Re-posicionar en caso de que cambie el tamaño del contenido o visibilidad

    def _on_toggle_html_table_preview(self, checked):
        # Si se activa y no hay contenido, intentar generarlo (sin guardar archivo)
        if checked and not self.generated_html_content:
            # Generar HTML solo para preview, sin diálogo de guardado
            project_name = self.le_nombre.text().strip() or "Vista Previa"
            table_data = []
            for r in range(self.table.rowCount()): # Similar a _on_generate_html_table
                id_item = self.table.item(r,0); x_item = self.table.item(r,1); y_item = self.table.item(r,2)
                if x_item and y_item and x_item.text().strip() and y_item.text().strip():
                    try:
                        x_val = float(x_item.text()); y_val = float(y_item.text())
                        row_id = id_item.text().strip() if id_item else str(r+1)
                        table_data.append((row_id, f"{x_val:.2f}", f"{y_val:.2f}"))
                    except ValueError: continue

            if not table_data: # No generar preview si no hay datos
                self.html_preview_widget.setHtml("<html><body><p>No hay datos válidos en la tabla para generar la previsualización.</p></body></html>")
                self.html_preview_widget.show()
                self._position_canvas_widgets()
                return

            mgr = self._build_manager_from_table()
            perimetro_str = "N/A"; area_str = "N/A"
            if mgr:
                active_features = mgr.get_features()
                if active_features:
                    first_linestring_coords = None; first_polygon_coords = None
                    for feat in active_features:
                        if feat["type"] == GeometryType.POLILINEA and not first_linestring_coords: first_linestring_coords = feat["coords"]
                        if feat["type"] == GeometryType.POLIGONO and not first_polygon_coords: first_polygon_coords = feat["coords"]
                    if first_polygon_coords:
                        poly_perimeter_coords = first_polygon_coords + [first_polygon_coords[0]]
                        perimetro_str = f"{self._calculate_length(poly_perimeter_coords):.2f} m"
                        area_str = f"{self._calculate_polygon_area(first_polygon_coords):.2f} m²"
                    elif first_linestring_coords:
                        perimetro_str = f"{self._calculate_length(first_linestring_coords):.2f} m (Polilínea)"; area_str = "N/A (es Polilínea)"

            html_preview = f"""<html><head><title>Preview - {project_name}</title><style>table{{border-collapse:collapse;}} th,td{{border:1px solid #ccc;padding:4px;text-align:center;}}</style></head><body>
                             <table><tr><th colspan="3">{project_name} (Preview)</th></tr><tr><th>No</th><th>X</th><th>Y</th></tr>"""
            for row in table_data: html_preview += f"<tr><td>{row[0]}</td><td>{row[1]}</td><td>{row[2]}</td></tr>"
            html_preview += f"<tr><td colspan='3'>Perímetro: {perimetro_str}</td></tr><tr><td colspan='3'>Área: {area_str}</td></tr></table></body></html>"
            self.generated_html_content = html_preview # Guardar para que no se regenere si solo se oculta/muestra

        self._update_html_preview()


    # --- Métodos existentes ---
    def _on_cell_changed(self, item):
        r, c = item.row(), item.column()
        if c in (1,2):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                if r == self.table.rowCount()-1:
                    self.table.insertRow(self.table.rowCount())
                    id_item = QTableWidgetItem(str(self.table.rowCount()))
                    id_item.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(self.table.rowCount()-1, 0, id_item)
        try:
            self._clear_canvas_error()
            mgr = self._build_manager_from_table()
            if mgr is not None: self._redraw_scene(mgr)
            self.generated_html_content = None # Resetear HTML cache para que se regenere en preview si es necesario
            self._update_html_preview() # Actualizar preview si está visible
        except (ValueError, TypeError) as e:
            print(f"Error al construir features para preview: {e}")

    def _on_cell_clicked(self, row, col):
        if col == 0: self.table.selectRow(row); self.table.setCurrentCell(row,1)

    def _show_table_menu(self, pos):
        menu = QMenu(); menu.addAction("Eliminar fila(s)", self._delete_selected_rows)
        menu.addSeparator(); menu.addAction("Copiar", self._copy_selection); menu.addAction("Pegar", self._paste_to_table)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selection(self):
        ranges = self.table.selectedRanges()
        if not ranges: return
        text = ""
        for r_range in ranges:
            for r in range(r_range.topRow(), r_range.bottomRow()+1):
                parts = []
                for col in range(r_range.leftColumn(), r_range.rightColumn()+1):
                    itm = self.table.item(r,col); parts.append(itm.text() if itm else "")
                text += "\t".join(parts) + "\n"
        QApplication.clipboard().setText(text)

    def _delete_selected_rows(self):
        selected_rows = sorted(list(set(index.row() for index in self.table.selectedIndexes())), reverse=True)
        if not selected_rows:
            current_row = self.table.currentRow()
            if current_row >= 0: selected_rows = [current_row]
        for row in selected_rows: self.table.removeRow(row)
        for r_idx in range(self.table.rowCount()):
            id_item = self.table.item(r_idx, 0); new_id = str(r_idx + 1)
            if not id_item: id_item = QTableWidgetItem(new_id); id_item.setFlags(Qt.ItemIsEnabled); self.table.setItem(r_idx, 0, id_item)
            else: id_item.setText(new_id)
        if self.table.rowCount() == 0:
            self.table.insertRow(0); id_item = QTableWidgetItem("1"); id_item.setFlags(Qt.ItemIsEnabled); self.table.setItem(0, 0, id_item)
        elif self.table.rowCount() > 0:
            last_row_idx = self.table.rowCount() - 1
            item_x = self.table.item(last_row_idx, 1); item_y = self.table.item(last_row_idx, 2)
            if (item_x and item_x.text().strip()) or (item_y and item_y.text().strip()):
                self.table.insertRow(self.table.rowCount())
                id_item = QTableWidgetItem(str(self.table.rowCount())); id_item.setFlags(Qt.ItemIsEnabled); self.table.setItem(self.table.rowCount() -1, 0, id_item)
        try:
            self._clear_canvas_error(); mgr = self._build_manager_from_table()
            if mgr is not None: self._redraw_scene(mgr)
            self.generated_html_content = None; self._update_html_preview()
        except (ValueError, TypeError) as e: print(f"Error al construir features tras eliminar fila(s): {e}")

    def _paste_to_table(self):
        text = QApplication.clipboard().text(); lines = text.splitlines()
        if not lines: return
        start_row = self.table.currentRow()
        if start_row == -1:
            for r_idx in range(self.table.rowCount()):
                item_x = self.table.item(r_idx, 1); item_y = self.table.item(r_idx, 2)
                if (not item_x or not item_x.text().strip()) and (not item_y or not item_y.text().strip()): start_row = r_idx; break
            else: start_row = self.table.rowCount() -1
        last_id = 0
        for r_idx in range(self.table.rowCount() -1, -1, -1):
            id_item = self.table.item(r_idx, 0)
            if id_item and id_item.text().strip():
                try: last_id = int(id_item.text().strip()); break
                except ValueError: continue
        next_id_to_assign = last_id
        is_first_row_empty = False
        if start_row == 0 and self.table.rowCount() == 1:
            item_x = self.table.item(0, 1); item_y = self.table.item(0, 2)
            if (not item_x or not item_x.text().strip()) and (not item_y or not item_y.text().strip()): is_first_row_empty = True
        if not is_first_row_empty: next_id_to_assign = last_id + 1
        rows_pasted_count = 0
        for line_idx, line_text in enumerate(lines):
            line_text = line_text.strip()
            if not line_text: continue
            try:
                parts = re.split(r'[\s,;\t]+', line_text); parts = [p.strip() for p in parts if p.strip()]
                if len(parts) >= 2:
                    x_str = parts[0].replace(',', '.'); y_str = parts[1].replace(',', '.')
                    x_val = float(x_str); y_val = float(y_str)
                    current_target_row = start_row + rows_pasted_count
                    if is_first_row_empty and rows_pasted_count == 0: current_target_row = 0
                    elif current_target_row >= self.table.rowCount():
                        self.table.insertRow(current_target_row)
                        id_item = QTableWidgetItem(str(next_id_to_assign)); id_item.setFlags(Qt.ItemIsEnabled)
                        self.table.setItem(current_target_row, 0, id_item); next_id_to_assign +=1
                    else:
                        id_item_existing = self.table.item(current_target_row, 0)
                        if not id_item_existing or not id_item_existing.text().strip():
                            id_item = QTableWidgetItem(str(next_id_to_assign)); id_item.setFlags(Qt.ItemIsEnabled)
                            self.table.setItem(current_target_row, 0, id_item); next_id_to_assign += 1
                    self.table.setItem(current_target_row, 1, QTableWidgetItem(f"{x_val:.6f}"))
                    self.table.setItem(current_target_row, 2, QTableWidgetItem(f"{y_val:.6f}"))
                    rows_pasted_count += 1
                else: print(f"Advertencia: Línea '{line_text}' no tiene suficientes datos X,Y. Omitida.")
            except ValueError: print(f"Advertencia: Línea '{line_text}' contiene datos X,Y no numéricos. Omitida.")
            except Exception as e: print(f"Error procesando línea '{line_text}': {e}. Omitida.")
        if rows_pasted_count > 0:
            last_modified_row = start_row + rows_pasted_count - 1
            last_item = self.table.item(last_modified_row, 2)
            if last_item: self._on_cell_changed(last_item)
            else:
                 try:
                    self._clear_canvas_error(); mgr = self._build_manager_from_table()
                    if mgr is not None: self._redraw_scene(mgr)
                    self.generated_html_content = None; self._update_html_preview()
                 except (ValueError, TypeError) as e: print(f"Error al construir features tras completar pegado: {e}")

    def _build_manager_from_table(self):
        self._clear_canvas_error()
        coords = []
        for r in range(self.table.rowCount()):
            item_x = self.table.item(r, 1); item_y = self.table.item(r, 2)
            if item_x and item_y and item_x.text().strip() and item_y.text().strip():
                try:
                    x_val = float(item_x.text()); y_val = float(item_y.text())
                    coords.append((x_val, y_val))
                except ValueError:
                    print(f"Advertencia: Coordenadas inválidas en fila {r+1} omitidas: '{item_x.text()}', '{item_y.text()}'")
                    continue
        try: current_zone = int(self.cb_zona.currentText())
        except ValueError: self._show_canvas_error("Error: La Zona UTM seleccionada no es un número válido."); return None
        mgr = CoordinateManager(hemisphere=self.cb_hemisferio.currentText(), zone=current_zone)
        feature_id_counter = 1
        polilinea_ok = True
        if self.chk_polilinea.isChecked():
            if len(coords) < 2 : self._show_canvas_error("Polilínea: Se necesitan al menos 2 coordenadas."); polilinea_ok = False
            elif coords:
                try: mgr.add_feature(feature_id_counter, GeometryType.POLILINEA, coords); feature_id_counter += 1
                except (ValueError, TypeError) as e: QMessageBox.warning(self, "Error al Crear Polilínea", f"{e}"); polilinea_ok = False
        poligono_ok = True
        if self.chk_poligono.isChecked():
            if len(coords) < 3:
                if polilinea_ok: self._show_canvas_error("Polígono: Se necesitan al menos 3 coordenadas."); poligono_ok = False
            elif coords:
                try: mgr.add_feature(feature_id_counter, GeometryType.POLIGONO, coords); feature_id_counter += 1
                except (ValueError, TypeError) as e: QMessageBox.warning(self, "Error al Crear Polígono", f"{e}"); poligono_ok = False
        if self.chk_punto.isChecked() and coords:
            if not ( (self.chk_polilinea.isChecked() and not polilinea_ok) or \
                     (self.chk_poligono.isChecked() and not poligono_ok) ):
                 self._clear_canvas_error()
            for i, (x,y) in enumerate(coords):
                try:
                    row_id_item = self.table.item(i, 0); point_id = feature_id_counter
                    if row_id_item and row_id_item.text().strip():
                        try: point_id = int(row_id_item.text().strip())
                        except ValueError: pass
                    mgr.add_feature(point_id, GeometryType.PUNTO, [(x,y)])
                except (ValueError, TypeError) as e: QMessageBox.warning(self, "Error al Crear Punto", f"No se pudo crear el punto para la coordenada ({x},{y}): {e}")
        return mgr

    def _redraw_scene(self, mgr):
        self.scene.clear();
        if not mgr: return
        if self.chk_punto.isChecked():
            for feat in mgr.get_features():
                if feat["type"] == GeometryType.PUNTO:
                    if feat["coords"] and isinstance(feat["coords"], list) and len(feat["coords"]) > 0:
                        coord_pair = feat["coords"][0]
                        if isinstance(coord_pair, (list, tuple)) and len(coord_pair) == 2:
                            x,y = coord_pair; self.scene.addEllipse(x-3, y-3, 6, 6, QPen(Qt.red), QBrush(Qt.red))
        features_for_builder = mgr.get_features()
        for path, pen in GeometryBuilder.paths_from_features(features_for_builder): self.scene.addPath(path, pen)

    def _on_guardar(self):
        dirp = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de proyecto");
        if not dirp: return
        proj = self.le_nombre.text().strip() or "proyecto"; full_path_filename = os.path.join(dirp, proj + self.cb_format.currentText())
        try: mgr = self._build_manager_from_table();
            if mgr is None: return
        except (ValueError, TypeError) as e: QMessageBox.critical(self, "Error en Datos de Tabla", f"No se pueden generar geometrías: {e}"); return
        selected_format = self.cb_format.currentText(); features_to_export = mgr.get_features()
        if not features_to_export: QMessageBox.warning(self, "Nada para Exportar", "No hay geometrías definidas para exportar."); return
        hemisphere = self.cb_hemisferio.currentText(); zone = self.cb_zona.currentText()
        try:
            export_successful = False
            if selected_format == ".kml": KMLExporter.export(features_to_export, full_path_filename, hemisphere, zone); export_successful = True
            elif selected_format == ".kmz": KMZExporter.export(features_to_export, full_path_filename, hemisphere, zone); export_successful = True
            elif selected_format == ".shp": ShapefileExporter.export(features_to_export, full_path_filename, hemisphere, zone); export_successful = True
            else: QMessageBox.warning(self, "Formato no Soportado", f"Exportación a '{selected_format}' no implementada."); return
            if export_successful: QMessageBox.information(self, "Éxito", f"Archivo guardado en:\n{full_path_filename}")
        except ImportError as ie: QMessageBox.critical(self, "Error de Dependencia", f"No se pudo exportar a '{selected_format}'. Faltante: {str(ie)}.")
        except (ValueError, RuntimeError) as e: QMessageBox.critical(self, "Error de Exportación", f"Error al exportar a '{selected_format}':\n{str(e)}")
        except Exception as e: QMessageBox.critical(self, "Error al Guardar", f"Error inesperado al guardar en '{selected_format}':\n{str(e)}")

    def _on_export(self): self._on_guardar()
    def _on_new(self):
        self._clear_canvas_error(); self.generated_html_content = None; self._update_html_preview()
        self.table.setRowCount(0); self.table.setRowCount(1)
        first = QTableWidgetItem("1"); first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first); self.table.setItem(0,1, QTableWidgetItem("")); self.table.setItem(0,2, QTableWidgetItem(""))
        if self.scene: self.scene.clear()
        self.chk_punto.setChecked(False); self.chk_polilinea.setChecked(False); self.chk_poligono.setChecked(False)
        self.le_nombre.clear()

    def _on_open(self):
        filters = "Archivos de Proyecto SIG (*.kml *.kmz *.shp);;Todos los archivos (*)"
        path, _ = QFileDialog.getOpenFileName(self, "Abrir Proyecto", "", filters)
        if path: QMessageBox.information(self, "Abrir Proyecto", f"Funcionalidad de abrir proyecto '{path}' aún no implementada.")

    def _on_import(self):
        self._clear_canvas_error(); self.generated_html_content = None; self._update_html_preview()
        filters = "Archivos de Coordenadas (*.csv *.txt);;Archivos KML (*.kml);;Todos los archivos (*)"
        path, selected_filter = QFileDialog.getOpenFileName(self, "Importar Coordenadas o Geometrías", "", filters)
        if not path: return
        file_ext = os.path.splitext(path)[1].lower()
        imported_features = []; import_source_type = ""
        try:
            if file_ext in ['.csv', '.txt']:
                imported_features = CSVImporter.import_file(path); import_source_type = "CSV"
            elif file_ext == '.kml':
                hemisphere = self.cb_hemisferio.currentText(); zone_str = self.cb_zona.currentText()
                if not zone_str: QMessageBox.warning(self, "Zona no Seleccionada", "Seleccione zona UTM para importar KML."); return
                zone = int(zone_str)
                imported_features = KMLImporter.import_file(path, hemisphere, zone); import_source_type = "KML"
            else: QMessageBox.warning(self, "Formato no Soportado", f"Importación de '{file_ext}' no implementada."); return
            if not imported_features:
                QMessageBox.information(self, f"Importación {import_source_type}", f"No se importaron geometrías de {os.path.basename(path)}."); return
            self._on_new()
            self.table.setRowCount(len(imported_features))
            for i, feat in enumerate(imported_features):
                id_item = QTableWidgetItem(str(feat.get("id", i + 1))); id_item.setFlags(Qt.ItemIsEnabled); self.table.setItem(i, 0, id_item)
                coords = feat.get("coords"); geom_type = feat.get("type")
                if geom_type == GeometryType.PUNTO and coords and len(coords) == 1 and isinstance(coords[0],(list,tuple)) and len(coords[0])==2:
                    self.table.setItem(i, 1, QTableWidgetItem(f"{coords[0][0]:.6f}")); self.table.setItem(i, 2, QTableWidgetItem(f"{coords[0][1]:.6f}"))
                else: self.table.setItem(i, 1, QTableWidgetItem("")); self.table.setItem(i, 2, QTableWidgetItem(f"({geom_type})" if geom_type else ""))
            if import_source_type == "CSV": self.chk_punto.setChecked(True)
            mgr = self._build_manager_from_table();
            if mgr is not None: self._redraw_scene(mgr)
            success_msg = f"{len(imported_features)} geometrías importadas de {os.path.basename(path)}."
            if import_source_type == "KML": success_msg += "\nActive los checkboxes de tipo para visualizar."
            QMessageBox.information(self, f"Importación {import_source_type} Exitosa", success_msg)
        except FileNotFoundError: QMessageBox.critical(self, "Error de Importación", f"Archivo no encontrado: {path}")
        except (RuntimeError, ValueError, ProjError) as e: QMessageBox.critical(self, f"Error de Importación {import_source_type}", f"Error: {e}")
        except Exception as e: QMessageBox.critical(self, "Error Inesperado", f"Error inesperado en importación: {e}")

    def _on_undo(self): QMessageBox.information(self, "Deshacer", "Funcionalidad no implementada.")
    def _on_redo(self): QMessageBox.information(self, "Rehacer", "Funcionalidad no implementada.")
    def _on_settings(self): ConfigDialog(self).exec()
    def _on_help(self): HelpDialog(self).exec()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
