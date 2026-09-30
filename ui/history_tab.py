"""History tab: browse and inspect previously saved local reviews."""
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from core.db import Database


class HistoryTab(QWidget):
    def __init__(self, db: Database, parent=None):
        super().__init__(parent)
        self.db = db
        self._records = []
        self._build_ui()
        self.reload()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date", "Provider", "Title / URL", "Verdict", "Notified"])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        button_row = QHBoxLayout()
        self.load_button = QPushButton("Load Selected Report")
        self.refresh_button = QPushButton("Refresh")
        self.delete_button = QPushButton("Delete Selected")
        button_row.addWidget(self.load_button)
        button_row.addWidget(self.refresh_button)
        button_row.addWidget(self.delete_button)
        button_row.addStretch(1)

        self.report_viewer = QTextBrowser()

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self.table)
        splitter.addWidget(self.report_viewer)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)

        layout.addLayout(button_row)
        layout.addWidget(splitter)

        self.load_button.clicked.connect(self._on_load_clicked)
        self.refresh_button.clicked.connect(self.reload)
        self.delete_button.clicked.connect(self._on_delete_clicked)
        self.table.doubleClicked.connect(self._on_load_clicked)

    def reload(self) -> None:
        self._records = self.db.get_all()
        self.table.setRowCount(len(self._records))
        for row, record in enumerate(self._records):
            self.table.setItem(row, 0, QTableWidgetItem(record.created_at))
            self.table.setItem(row, 1, QTableWidgetItem(record.provider))
            self.table.setItem(row, 2, QTableWidgetItem(record.title or record.url))
            self.table.setItem(row, 3, QTableWidgetItem(record.verdict))
            self.table.setItem(row, 4, QTableWidgetItem("Yes" if record.notified else "No"))

    def _selected_record(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        index = rows[0].row()
        if 0 <= index < len(self._records):
            return self._records[index]
        return None

    def _on_load_clicked(self) -> None:
        record = self._selected_record()
        if not record:
            QMessageBox.information(self, "No Selection", "Select a row first.")
            return
        self.report_viewer.setMarkdown(record.report_markdown or "_No report content saved._")

    def _on_delete_clicked(self) -> None:
        record = self._selected_record()
        if not record:
            return
        confirm = QMessageBox.question(
            self, "Delete Review", f"Delete the saved review for '{record.title}'?"
        )
        if confirm == QMessageBox.StandardButton.Yes:
            self.db.delete(record.id)
            self.reload()
            self.report_viewer.clear()
