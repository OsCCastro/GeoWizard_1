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
from core.coordinate_manager import CoordinateManager
from exporters.kml_exporter import KMLExporter
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
        model.setData(index, text)
        # solo cambia color de texto si no está seleccionado
        if not (model.data(index, Qt.ItemIsSelectable) and
                model.data(index, Qt.BackgroundRole)):
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
        mgr = self._build_manager_from_table()
        self._redraw_scene(mgr)

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

    def _paste_to_table(self):
        lines = QApplication.clipboard().text().splitlines()
        r = self.table.currentRow()
        for ln in lines:
            pts = [p.strip() for p in ln.split(",")]
            if len(pts) >= 2:
                try:
                    float(pts[0]); float(pts[1])
                except ValueError:
                    continue
                if r >= self.table.rowCount():
                    self.table.insertRow(r)
                    id_it = QTableWidgetItem(str(r+1))
                    id_it.setFlags(Qt.ItemIsEnabled)
                    self.table.setItem(r,0,id_it)
                self.table.setItem(r,1, QTableWidgetItem(pts[0]))
                self.table.setItem(r,2, QTableWidgetItem(pts[1]))
                r += 1

    def _build_manager_from_table(self):
        coords = []
        for r in range(self.table.rowCount()):
            xi = self.table.item(r,1); yi = self.table.item(r,2)
            if xi and yi and xi.text().strip() and yi.text().strip():
                try:
                    coords.append((float(xi.text()), float(yi.text())))
                except ValueError:
                    pass
        mgr = CoordinateManager(
            hemisphere=self.cb_hemisferio.currentText(),
            zone=int(self.cb_zona.currentText())
        )
        nid = 1
        if self.chk_punto.isChecked():
            for x,y in coords:
                mgr.add_feature(nid, "Point", [(x,y)])
                nid += 1
        if self.chk_polilinea.isChecked() and len(coords) >= 2:
            mgr.add_feature(nid, "LineString", coords)
            nid += 1
        if self.chk_poligono.isChecked() and len(coords) >= 3:
            # cierre de anillo solo para Polygon
            mgr.add_feature(nid, "Polygon", coords + [coords[0]])
            nid += 1
        return mgr

    def _redraw_scene(self, mgr):
        self.scene.clear()
        # puntos primero
        if self.chk_punto.isChecked():
            for feat in mgr.get_features():
                if feat["type"] == "Point":
                    x,y = feat["coords"][0]
                    self.scene.addEllipse(x-3, y-3, 6, 6,
                                        QPen(Qt.red), QBrush(Qt.red))
        # luego líneas/polígonos
        for path, pen in GeometryBuilder.paths_from_features(mgr.get_features()):
            self.scene.addPath(path, pen)

    def _on_guardar(self):
        dirp = QFileDialog.getExistingDirectory(self, "Seleccionar carpeta de proyecto")
        if not dirp:
            return
        proj = self.le_nombre.text().strip() or "proyecto"
        full = os.path.join(dirp, proj + self.cb_format.currentText())
        mgr = self._build_manager_from_table()
        try:
            KMLExporter.export(
                mgr.get_features(), full,
                hemisphere=self.cb_hemisferio.currentText(),
                zone=self.cb_zona.currentText()
            )
            QMessageBox.information(self, "Éxito", f"Archivo guardado en:\n{full}")
        except Exception as e:
            QMessageBox.critical(self, "Error al guardar", str(e))

    def _on_export(self):
        self._on_guardar()

    def _on_new(self):
        self.table.clearContents()
        self.table.setRowCount(1)
        first = QTableWidgetItem("1"); first.setFlags(Qt.ItemIsEnabled)
        self.table.setItem(0,0,first)
        self.scene.clear()

    def _on_open(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Abrir proyecto", "", "SIG Files (*.kml *.kmz *.shp *.csv *.txt)"
        )
        if path:
            print(f"Abrir proyecto: {path}")

    def _on_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Importar coordenadas", "", "Coordenadas (*.csv *.txt *.kml)"
        )
        if path:
            print(f"Importar desde: {path}")

    def _on_undo(self):
        print("Deshacer acción")

    def _on_redo(self):
        print("Rehacer acción")

    def _on_settings(self):
        ConfigDialog(self).exec()

    def _on_help(self):
        HelpDialog(self).exec()

if __name__ == "__main__":
    import sys
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
