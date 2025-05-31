import os
from PySide6.QtCore import Qt, QRegularExpression, QPointF, QItemSelectionModel
from PySide6.QtGui import (
    QAction,
    QRegularExpressionValidator,
    QBrush,
    QPainterPath,
    QPen
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
    QTableWidgetItem
)

from config_dialog import ConfigDialog
from help_dialog import HelpDialog
from core.coordinate_manager import CoordinateManager, GeometryType
from exporters.kml_exporter import KMLExporter
from exporters.kmz_exporter import KMZExporter # Asumiendo que existe
from exporters.shapefile_exporter import ShapefileExporter # Asumiendo que existe
from importers.csv_importer import CSVImporter
from importers.kml_importer import KMLImporter # Importar KMLImporter
from core.geometry import GeometryBuilder


class UTMDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = super().createEditor(parent, option, index)
        # 6-7 dígitos + decimales opcionales
        rx = QRegularExpression(r'^\d{6,7}(\.\d+)?$')
        editor.setValidator(QRegularExpressionValidator(rx, editor))
        return editor

    def setModelData(self, editor, model, index):
        text = editor.text()
        model.setData(index, text) # Set the actual data
        # Always apply foreground color based on input validity for cells managed by this delegate
        color = Qt.black if editor.hasAcceptableInput() else Qt.red
        model.setData(index, QBrush(color), Qt.ForegroundRole)

class CoordTable(QTableWidget):
    def keyPressEvent(self, event):
        # Tab: al salir de Y, saltar a X de la siguiente fila
        if event.key() == Qt.Key_Tab and self.currentColumn() == 2:
            self.setCurrentCell(self.currentRow() + 1, 1)
            return
        super().keyPressEvent(event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SIG: Gestión de Coordenadas")
        self._build_ui()
        self._create_toolbar()

    def _build_ui(self):
        central = QWidget()
        main_layout = QHBoxLayout(central)

        #######################
        # Panel de controles  #
        #######################
        control = QVBoxLayout()

        # Hemisferio / Zona
        hz = QHBoxLayout()
        hz.addWidget(QLabel("Hemisferio:"))
        self.cb_hemisferio = QComboBox()
        self.cb_hemisferio.addItems(["Norte","Sur"])
        hz.addWidget(self.cb_hemisferio)
        hz.addWidget(QLabel("Zona UTM:"))
        self.cb_zona = QComboBox()
        self.cb_zona.addItems([str(i) for i in range(1,61)])
        hz.addWidget(self.cb_zona)
        control.addLayout(hz)

        # Tabla de coordenadas
        self.table = CoordTable(1,3)
        self.table.setHorizontalHeaderLabels(["ID","X (Este)","Y (Norte)"])
        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        # primer ID
        first = QTableWidgetItem("1")
        first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first)
        # validación UTM
        delegate = UTMDelegate(self.table)
        self.table.setItemDelegateForColumn(1, delegate)
        self.table.setItemDelegateForColumn(2, delegate)
        # selección y menú contextual
        self.table.setSelectionBehavior(QTableWidget.SelectItems)
        self.table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table.itemChanged.connect(self._on_cell_changed)
        self.table.cellClicked.connect(self._on_cell_clicked)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_table_menu)
        control.addWidget(self.table)

        # Geometrías
        geo = QHBoxLayout()
        geo.addWidget(QLabel("Geometría:"))
        self.chk_punto     = QCheckBox("Punto")
        self.chk_polilinea = QCheckBox("Polilínea")
        self.chk_poligono  = QCheckBox("Polígono")
        geo.addWidget(self.chk_punto)
        geo.addWidget(self.chk_polilinea)
        geo.addWidget(self.chk_poligono)
        control.addLayout(geo)

        # Mapa base
        self.chk_mapbase = QCheckBox("Usar mapa base (OSM)")
        control.addWidget(self.chk_mapbase)

        # Proyecto / Formato
        ff = QHBoxLayout()
        ff.addWidget(QLabel("Proyecto:"))
        self.le_nombre = QLineEdit()
        ff.addWidget(self.le_nombre)
        ff.addWidget(QLabel("Formato:"))
        self.cb_format = QComboBox()
        self.cb_format.addItems([".kml",".kmz",".shp"])
        ff.addWidget(self.cb_format)
        control.addLayout(ff)

        # Botón seleccionar carpeta
        bl = QHBoxLayout()
        bl.addStretch()
        btn = QPushButton("Seleccionar carpeta")
        btn.clicked.connect(self._on_guardar)
        bl.addWidget(btn)
        control.addLayout(bl)

        ##################
        # Lienzo (canvas)#
        ##################
        self.canvas = QGraphicsView()
        self.scene  = QGraphicsScene(self.canvas)
        self.canvas.setScene(self.scene)
        self.canvas.setMinimumSize(400,300)
        self.canvas.setStyleSheet("background-color:white; border:1px solid #ccc; padding:8px;")

        # ensamblar
        main_layout.addLayout(control,1)
        main_layout.addWidget(self.canvas,2)
        self.setCentralWidget(central)

    def _create_toolbar(self):
        tb = QToolBar("Principal")
        self.addToolBar(tb)

        # acciones básicas
        for ico, text, slot in [
            (QStyle.SP_FileIcon,        "Nuevo",    self._on_new),
            (QStyle.SP_DialogOpenButton,"Abrir",    self._on_open),
            (QStyle.SP_DialogSaveButton,"Guardar",  self._on_guardar),
            (QStyle.SP_DirOpenIcon,     "Importar", self._on_import),
            (QStyle.SP_DialogSaveButton,"Exportar", self._on_export)
        ]:
            a = QAction(self.style().standardIcon(ico), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        tb.addSeparator()

        # deshacer / rehacer
        for ico, text, slot in [
            (QStyle.SP_ArrowBack,   "Deshacer", self._on_undo),
            (QStyle.SP_ArrowForward,"Rehacer",  self._on_redo),
        ]:
            a = QAction(self.style().standardIcon(ico), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

        tb.addSeparator()

        # mostrar/ocultar lienzo
        tog = QAction(self.style().standardIcon(QStyle.SP_TitleBarMaxButton),
                      "Mostrar/Ocultar lienzo", self)
        tog.setCheckable(True); tog.setChecked(True)
        tog.toggled.connect(self.canvas.setVisible)
        tb.addAction(tog)

        tb.addSeparator()

        # modo oscuro
        theme = QAction(self.style().standardIcon(QStyle.SP_DialogYesButton),
                        "Modo oscuro", self)
        theme.setCheckable(True)
        theme.toggled.connect(lambda ch: QApplication.instance().setStyleSheet(
            "QWidget{background:#2b2b2b;color:#ddd;}" if ch else ""
        ))
        tb.addAction(theme)

        tb.addSeparator()

        # configuraciones y ayuda
        for ico, text, slot in [
            (QStyle.SP_FileDialogDetailedView,"Configuraciones",self._on_settings),
            (QStyle.SP_DialogHelpButton,       "Ayuda",self._on_help),
        ]:
            a = QAction(self.style().standardIcon(ico), text, self)
            a.triggered.connect(slot)
            tb.addAction(a)

    def _on_cell_changed(self, item):
        r, c = item.row(), item.column()
        # auto-agregar fila nueva
        if c in (1,2):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                if r == self.table.rowCount()-1:
                    nr = self.table.rowCount()
                    self.table.insertRow(nr)
                    id_it = QTableWidgetItem(str(nr+1))
                    id_it.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(nr,0,id_it)
        # refresca preview
        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
            print(f"Error al construir features para preview: {e}")


    def _on_cell_clicked(self, row, col):
        if col == 0:
            sel = self.table.selectionModel()
            sel.clearSelection()
            for cc in (1,2):
                idx = self.table.model().index(row,cc)
                sel.select(idx, QItemSelectionModel.Select)
            self.table.setCurrentCell(row,1)

    def _show_table_menu(self, pos):
        menu = QMenu()
        menu.addAction("Eliminar fila", self._delete_row)
        menu.addSeparator()
        menu.addAction("Copiar", self._copy_selection)
        menu.addAction("Pegar", self._paste_to_table)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _copy_selection(self):
        ranges = self.table.selectedRanges()
        if not ranges:
            return
        text = ""
        for r in ranges:
            for row in range(r.topRow(), r.bottomRow()+1):
                parts = []
                for col in range(r.leftColumn(), r.rightColumn()+1):
                    itm = self.table.item(row,col)
                    parts.append(itm.text() if itm else "")
                text += "\t".join(parts) + "\n"
        QApplication.clipboard().setText(text)

    def _delete_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
            print(f"Error al construir features para preview tras eliminar fila: {e}")


    def _paste_to_table(self):
        lines = QApplication.clipboard().text().splitlines()
        r = self.table.currentRow()
        if r < 0:
            r = 0
            if self.table.item(r,0) and not (self.table.item(r,0).flags() & Qt.ItemIsEditable):
                pass

        for ln_idx, ln in enumerate(lines):
            if not ln.strip():
                continue

            current_id_item = self.table.item(r, 0)
            is_id_cell_uneditable = current_id_item and not (current_id_item.flags() & Qt.ItemIsEditable)

            if r >= self.table.rowCount():
                self.table.insertRow(r)
                id_it = QTableWidgetItem(str(r+1))
                id_it.setFlags(Qt.ItemIsEnabled)
                self.table.setItem(r,0,id_it)
            elif is_id_cell_uneditable and (self.table.item(r,1) and self.table.item(r,1).text() or \
                                          self.table.item(r,2) and self.table.item(r,2).text()):
                pass

            pts = [p.strip() for p in ln.split(",")]
            if len(pts) < 2:
                pts = [p.strip() for p in ln.split("\t")]

            if len(pts) >= 2:
                try:
                    float(pts[0].replace(',','.'))
                    float(pts[1].replace(',','.'))
                except ValueError:
                    QMessageBox.warning(self, "Error de Pegado", f"Línea '{ln}' no contiene coordenadas X,Y numéricas válidas.")
                    continue

                self.table.setItem(r,1, QTableWidgetItem(pts[0].replace(',','.')))
                self.table.setItem(r,2, QTableWidgetItem(pts[1].replace(',','.')))
                r += 1

        try:
            mgr = self._build_manager_from_table()
            self._redraw_scene(mgr)
        except (ValueError, TypeError) as e:
             print(f"Error al construir features para preview tras pegar: {e}")


    def _build_manager_from_table(self):
        coords = []
        for r in range(self.table.rowCount()):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                try:
                    x_val = float(xi.text())
                    y_val = float(yi.text())
                    coords.append((x_val, y_val))
                except ValueError:
                    pass

        mgr = CoordinateManager(
            hemisphere=self.cb_hemisferio.currentText(),
            zone=int(self.cb_zona.currentText())
        )
        nid = 1

        if coords:
            if self.chk_punto.isChecked():
                for x,y in coords:
                    try:
                        mgr.add_feature(nid, GeometryType.PUNTO, [(x,y)])
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Punto", f"Feature ID {nid}: {e}")

            if self.chk_polilinea.isChecked():
                if len(coords) >= 2:
                    try:
                        mgr.add_feature(nid, GeometryType.POLILINEA, coords)
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Polilínea", f"Feature ID {nid}: {e}")
                elif self.chk_polilinea.isEnabled() and self.chk_polilinea.isChecked():
                     QMessageBox.warning(self, "Datos insuficientes", "Se necesitan al menos 2 coordenadas para una Polilínea.")

            if self.chk_poligono.isChecked():
                if len(coords) >= 3:
                    try:
                        mgr.add_feature(nid, GeometryType.POLIGONO, coords)
                        nid += 1
                    except (ValueError, TypeError) as e:
                        QMessageBox.warning(self, "Error al crear Polígono", f"Feature ID {nid}: {e}")
                elif self.chk_poligono.isEnabled() and self.chk_poligono.isChecked():
                    QMessageBox.warning(self, "Datos insuficientes", "Se necesitan al menos 3 coordenadas para un Polígono.")
        return mgr

    def _redraw_scene(self, mgr):
        self.scene.clear()
        if not mgr:
            return

        if self.chk_punto.isChecked():
            for feat in mgr.get_features():
                if feat["type"] == GeometryType.PUNTO:
                    if feat["coords"]:
                        x,y = feat["coords"][0]
                        self.scene.addEllipse(x-3, y-3, 6, 6,
                                            QPen(Qt.red), QBrush(Qt.red))

        features_for_paths = mgr.get_features()
        for path, pen in GeometryBuilder.paths_from_features(features_for_paths):
            self.scene.addPath(path, pen)

    def _on_guardar(self):
        dirp = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de proyecto")
        if not dirp:
            return
        proj = self.le_nombre.text().strip() or "proyecto"
        full_path_filename = os.path.join(dirp, proj + self.cb_format.currentText())

        try:
            mgr = self._build_manager_from_table()
        except (ValueError, TypeError) as e:
            QMessageBox.critical(self, "Error en datos de tabla", f"No se pueden generar las geometrías para exportar: {e}")
            return

        selected_format = self.cb_format.currentText()

        features = mgr.get_features()
        if not features:
            QMessageBox.warning(self, "Nada para exportar", "No hay geometrías definidas para exportar.")
            return

        hemisphere = self.cb_hemisferio.currentText()
        zone = self.cb_zona.currentText()

        try:
            export_successful = False
            if selected_format == ".kml":
                KMLExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            elif selected_format == ".kmz":
                KMZExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            elif selected_format == ".shp":
                ShapefileExporter.export(features, full_path_filename, hemisphere, zone)
                export_successful = True
            else:
                QMessageBox.warning(self, "Formato no soportado",
                                    f"La exportación al formato '{selected_format}' aún no está implementada.")
                return

            if export_successful:
                QMessageBox.information(self, "Éxito", f"Archivo guardado en:\n{full_path_filename}")

        except ImportError as ie:
            QMessageBox.critical(self, "Error de dependencia",
                                 f"No se pudo exportar a '{selected_format}'. Dependencia faltante: {str(ie)}. Verifique la instalación.")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar",
                                 f"Ocurrió un error al guardar en formato '{selected_format}':\n{str(e)}")

    def _on_export(self):
        self._on_guardar()

    def _on_new(self):
        self.table.clearContents()
        self.table.setRowCount(1)
        first = QTableWidgetItem("1"); first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first)
        if self.scene:
            self.scene.clear()

        self.chk_punto.setChecked(False)
        self.chk_polilinea.setChecked(False)
        self.chk_poligono.setChecked(False)
        self.le_nombre.clear()

    def _on_open(self):
        filters = "Archivos de Proyecto SIG (*.kml *.kmz *.shp);;Todos los archivos (*)"
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir Proyecto", "", filters
        )
        if path:
            QMessageBox.information(self, "Abrir Proyecto", f"Funcionalidad de abrir proyecto '{path}' aún no implementada.")
            print(f"Abrir proyecto: {path}")

    def _on_import(self):
        filters = "Archivos de Coordenadas (*.csv *.txt);;Archivos KML (*.kml);;Todos los archivos (*)"
        path, selected_filter = QFileDialog.getOpenFileName(
            self, "Importar Coordenadas o Geometrías", "", filters
        )

        if not path:
            return

        file_ext = os.path.splitext(path)[1].lower()

        if file_ext in ['.csv', '.txt']:
            try:
                imported_features = CSVImporter.import_file(path)

                if not imported_features:
                    QMessageBox.information(self, "Importación CSV", "No se importaron geometrías válidas desde el archivo.")
                    return

                self._on_new()

                self.table.setRowCount(len(imported_features))
                for i, feat in enumerate(imported_features):
                    feat_id = feat.get("id", i + 1)
                    coords_list = feat.get("coords", [])

                    id_item = QTableWidgetItem(str(feat_id))
                    id_item.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(i, 0, id_item)

                    if coords_list and isinstance(coords_list[0], (list, tuple)) and len(coords_list[0]) == 2:
                        x_coord, y_coord = coords_list[0]
                        self.table.setItem(i, 1, QTableWidgetItem(str(x_coord if x_coord is not None else "")))
                        self.table.setItem(i, 2, QTableWidgetItem(str(y_coord if y_coord is not None else "")))
                    else:
                        self.table.setItem(i, 1, QTableWidgetItem(""))
                        self.table.setItem(i, 2, QTableWidgetItem(""))
                        print(f"Advertencia: Feature ID {feat_id} importado sin coordenadas válidas.")

                self.chk_punto.setChecked(True)
                self.chk_polilinea.setChecked(False)
                self.chk_poligono.setChecked(False)

                try:
                    mgr = self._build_manager_from_table()
                    self._redraw_scene(mgr)
                    QMessageBox.information(self, "Importación CSV Exitosa",
                                            f"{len(imported_features)} puntos importados desde {os.path.basename(path)}.")
                except (ValueError, TypeError) as e:
                    QMessageBox.critical(self, "Error al procesar datos importados",
                                         f"Los datos CSV importados no pudieron ser procesados: {e}")

            except FileNotFoundError:
                QMessageBox.critical(self, "Error de Importación", f"Archivo no encontrado: {path}")
            except RuntimeError as e:
                QMessageBox.critical(self, "Error de Importación", f"Error al importar archivo CSV: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Error Inesperado", f"Ocurrió un error inesperado durante la importación CSV: {e}")

        elif file_ext == '.kml':
            try:
                hemisphere = self.cb_hemisferio.currentText()
                zone_str = self.cb_zona.currentText()
                if not zone_str:
                    QMessageBox.warning(self, "Zona no seleccionada", "Por favor, seleccione una zona UTM antes de importar KML.")
                    return
                zone = int(zone_str)

                imported_features = KMLImporter.import_file(path, hemisphere, zone)

                if not imported_features:
                    QMessageBox.information(self, "Importación KML", "No se importaron geometrías válidas desde el archivo KML.")
                    return

                self._on_new()

                self.table.setRowCount(len(imported_features))
                for i, feat in enumerate(imported_features):
                    id_item = QTableWidgetItem(str(feat.get("id", i + 1)))
                    id_item.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(i, 0, id_item)

                    coords = feat.get("coords")
                    geom_type_from_kml = feat.get("type") # "Punto", "Polilínea", "Polígono"

                    if geom_type_from_kml == GeometryType.PUNTO and coords and len(coords) == 1:
                        if isinstance(coords[0], (list,tuple)) and len(coords[0]) == 2:
                             x_coord, y_coord = coords[0]
                             self.table.setItem(i, 1, QTableWidgetItem(f"{x_coord:.2f}"))
                             self.table.setItem(i, 2, QTableWidgetItem(f"{y_coord:.2f}"))
                        else:
                             self.table.setItem(i, 1, QTableWidgetItem(""))
                             self.table.setItem(i, 2, QTableWidgetItem(""))
                             print(f"Advertencia: Feature Punto ID {feat.get('id')} con formato de coordenadas incorrecto en la importación KML.")
                    else:
                        self.table.setItem(i, 1, QTableWidgetItem(""))
                        self.table.setItem(i, 2, QTableWidgetItem(f"({geom_type_from_kml})")) # Indicar tipo en celda Y

                # No se cambian los checkboxes. El usuario debe seleccionar el tipo apropiado
                # para que _build_manager_from_table construya las geometrías deseadas.
                # Se informa al usuario.

                try:
                    mgr = self._build_manager_from_table()
                    self._redraw_scene(mgr)
                    QMessageBox.information(self, "Importación KML Exitosa",
                                            f"{len(imported_features)} geometrías importadas desde {os.path.basename(path)}.\n"
                                            "Active los checkboxes de tipo de geometría (Punto, Polilínea, Polígono)\n"
                                            "para visualizar y procesar los datos importados.")
                except (ValueError, TypeError) as e:
                     QMessageBox.critical(self, "Error al procesar datos KML importados",
                                          f"Los datos KML importados no pudieron ser procesados: {e}")

            except FileNotFoundError:
                QMessageBox.critical(self, "Error de Importación KML", f"Archivo no encontrado: {path}")
            except (RuntimeError, ValueError) as e:
                QMessageBox.critical(self, "Error de Importación KML", f"Error al importar archivo KML: {e}")
            except Exception as e:
                QMessageBox.critical(self, "Error Inesperado", f"Ocurrió un error inesperado durante la importación KML: {e}")
        else:
            QMessageBox.warning(self, "Formato no Soportado",
                                f"La importación del formato de archivo '{file_ext}' aún no está implementada.")

    def _on_undo(self):
        QMessageBox.information(self, "Deshacer", "Funcionalidad de Deshacer aún no implementada.")
        print("Deshacer acción")

    def _on_redo(self):
        QMessageBox.information(self, "Rehacer", "Funcionalidad de Rehacer aún no implementada.")
        print("Rehacer acción")

    def _on_settings(self):
        dialog = ConfigDialog(self)
        dialog.exec()

    def _on_help(self):
        dialog = HelpDialog(self)
        dialog.exec()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
