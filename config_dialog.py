from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QLineEdit, QCheckBox,
    QDialogButtonBox
)
from PySide6.QtCore import Qt

class ConfigDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuraciones")
        self._build_ui()

    def _build_ui(self):
        # Layout principal
        layout = QVBoxLayout(self)

        # Formulario de ajustes
        form = QFormLayout()
        # Modo oscuro
        self.theme_checkbox = QCheckBox()
        form.addRow("Tema oscuro:", self.theme_checkbox)

        # Precisión de decimales
        self.precision_edit = QLineEdit()
        self.precision_edit.setPlaceholderText("Ej. 2")
        form.addRow("Decimales (precisión):", self.precision_edit)

        # Carpeta por defecto
        self.default_dir_edit = QLineEdit()
        self.default_dir_edit.setPlaceholderText("Ruta por defecto")
        form.addRow("Carpeta por defecto:", self.default_dir_edit)

        layout.addLayout(form)

        # Botones Aceptar / Cancelar
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def get_values(self):
        """
        Devuelve un dict con los valores ingresados,
        tras un exec() exitoso.
        """
        return {
            "dark_mode":   self.theme_checkbox.isChecked(),
            "precision":   self.precision_edit.text().strip(),
            "default_dir": self.default_dir_edit.text().strip()
        }
