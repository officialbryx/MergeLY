"""Dark Qt stylesheet for the MergeLY desktop UI."""

DARK_STYLESHEET = """
QWidget {
    background-color: #1e1f22;
    color: #e6e6e6;
    font-size: 13px;
}

QMainWindow, QDialog {
    background-color: #1e1f22;
}

QGroupBox {
    border: 1px solid #3a3d41;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
    font-weight: 600;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #9cdcfe;
}

QTabWidget::pane {
    border: 1px solid #3a3d41;
    border-radius: 4px;
}

QTabBar::tab {
    background: #2b2d30;
    color: #cfcfcf;
    padding: 8px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}

QTabBar::tab:selected {
    background: #0e639c;
    color: #ffffff;
}

QTabBar::tab:hover {
    background: #3a3d41;
}

QLineEdit, QTextEdit, QTextBrowser, QComboBox, QSpinBox {
    background-color: #2b2d30;
    border: 1px solid #3a3d41;
    border-radius: 4px;
    padding: 4px 6px;
    selection-background-color: #0e639c;
}

QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
    border: 1px solid #0e639c;
}

QComboBox::drop-down {
    border: none;
}

QPushButton {
    background-color: #0e639c;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 6px 14px;
}

QPushButton:hover {
    background-color: #1177bb;
}

QPushButton:pressed {
    background-color: #0a4d7a;
}

QPushButton:disabled {
    background-color: #3a3d41;
    color: #7a7a7a;
}

QProgressBar {
    border: 1px solid #3a3d41;
    border-radius: 4px;
    text-align: center;
    background-color: #2b2d30;
}

QProgressBar::chunk {
    background-color: #0e639c;
    border-radius: 4px;
}

QTableWidget {
    background-color: #2b2d30;
    gridline-color: #3a3d41;
    selection-background-color: #0e639c;
    selection-color: #ffffff;
}

QHeaderView::section {
    background-color: #1e1f22;
    color: #cfcfcf;
    padding: 6px;
    border: 1px solid #3a3d41;
}

QRadioButton, QCheckBox {
    spacing: 6px;
}

QScrollBar:vertical {
    background: #1e1f22;
    width: 12px;
}

QScrollBar::handle:vertical {
    background: #3a3d41;
    border-radius: 6px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #4a4d51;
}

QStatusBar {
    background-color: #007acc;
    color: #ffffff;
}

QSplitter::handle {
    background-color: #3a3d41;
}

QLabel {
    background: transparent;
}
"""
