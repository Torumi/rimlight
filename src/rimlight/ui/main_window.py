"""Placeholder main window."""

from collections.abc import Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel, QMainWindow

from rimlight import __version__


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(f"rimlight {__version__}")
        label = QLabel("rimlight is pre-alpha.\nThe device protocol is not documented yet.")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(label)
        self.resize(480, 240)


def run(argv: Sequence[str]) -> int:
    app = QApplication(list(argv))
    window = MainWindow()
    window.show()
    return app.exec()
