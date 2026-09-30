"""Main window: hosts the Reviewer, History, and Settings tabs."""
from PySide6.QtWidgets import QMainWindow, QTabWidget

from core.config import ConfigManager
from core.db import Database
from ui.history_tab import HistoryTab
from ui.reviewer_tab import ReviewerTab
from ui.settings_tab import SettingsTab


class MainWindow(QMainWindow):
    def __init__(self, db: Database, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.db = db
        self.config = config

        self.setWindowTitle("MergeLY — AI Code Reviewer")
        self.resize(1200, 800)
        self.setMinimumSize(1000, 700)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.reviewer_tab = ReviewerTab(self.config, self.db)
        self.history_tab = HistoryTab(self.db)
        self.settings_tab = SettingsTab(self.config)

        self.tabs.addTab(self.reviewer_tab, "Reviewer")
        self.tabs.addTab(self.history_tab, "History")
        self.tabs.addTab(self.settings_tab, "Settings")

        self.settings_tab.credentials_saved.connect(self.reviewer_tab.reload_clients)
        self.reviewer_tab.review_saved.connect(self.history_tab.reload)

        self.statusBar().showMessage("Ready")

    def closeEvent(self, event) -> None:
        self.reviewer_tab.shutdown()
        super().closeEvent(event)
