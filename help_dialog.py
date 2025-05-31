from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QTextBrowser,
    QDialogButtonBox
)

class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ayuda")
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Área de texto para la ayuda
        self.text = QTextBrowser()
        self.text.setHtml("""
            <h2>Ayuda - SIG: Gestión de Coordenadas</h2>
            <p>Bienvenido al sistema de ayuda. Aquí encontrarás información sobre cada funcionalidad:</p>
            <ul>
              <li><b>Nuevo:</b> Inicia un proyecto en blanco.</li>
              <li><b>Abrir:</b> Carga un proyecto o coordenadas existentes (KML, KMZ, SHP, CSV, TXT).</li>
              <li><b>Guardar / Exportar:</b> Almacena tu proyecto en la carpeta seleccionada, con el nombre y formato indicados.</li>
              <li><b>Importar:</b> Trae coordenadas desde un archivo externo (CSV, TXT, KML).</li>
              <li><b>Deshacer / Rehacer:</b> Navega por el historial de cambios en tu tabla y lienzo.</li>
              <li><b>Mostrar/Ocultar lienzo:</b> Activa o desactiva la vista gráfica.</li>
              <li><b>Modo oscuro:</b> Alterna entre tema claro y oscuro.</li>
              <li><b>Configuraciones:</b> Ajustes de precisión, tema y rutas por defecto.</li>
            </ul>
            <p>Para más detalles, visita: <a href='https://tu-docs-sig.example.com'>Documentación en línea</a>.</p>
        """)
        layout.addWidget(self.text)

        # Botón Cerrar
        buttons = QDialogButtonBox(QDialogButtonBox.Close, parent=self)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
