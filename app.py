"""MergeLY entry point: dark-themed QApplication bootstrap."""
import sys

from PySide6.QtWidgets import QApplication

from core.config import ConfigManager
from core.db import Database
from ui.main_window import MainWindow
from ui.theme import DARK_STYLESHEET


def main() -> int:
    app = QApplication(sys.argv)
    app.setStyle("Fusion")  # ensures the dark stylesheet renders consistently on every platform
    app.setApplicationName("MergeLY")
    app.setOrganizationName("MergeLY")
    app.setStyleSheet(DARK_STYLESHEET)

    db = Database()  # creates local SQLite tables on first run
    config = ConfigManager()

    window = MainWindow(db=db, config=config)
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
